
# The one-point rule

The *one-point rule* is a simplification for quantified formulas: if a
variable `x` is constrained by an equality `x == e` where `e` does not itself
mention `x`, then `x` can only ever take the single value `e`, so the
quantifier over `x` can be dropped and `e` substituted for every other
occurrence of `x`. For an existential,

```
∃x. x == e && φ(x)   ≡   φ(e)
```

and for the dual, universal case the equality appears as the premise of an
implication instead of a conjunct:

```
∀x. x == e ⟹ φ(x)   ≡   φ(e)
```

Both read the same fact off the formula — `x` is pinned to `e` — but the
`∃`/`&&` shape is the one that shows up in practice here, since it is exactly
the shape of a `merc` goal's body: a conjunction of constraints over
existentially quantified variables.

## Example

Take the goal

```
map goal: Nat # Nat -> Bool;
var n, m: Nat;
eqn goal(n, m) = n == 5 && m == n;
```

Read as `∃n, m. n == 5 && m == n`, the first conjunct is already one-point
shaped: `n` is pinned to `5`. Substituting it away turns the second conjunct
into `m == 5`, which is itself one-point shaped for `m`. Applying the rule
twice — once per conjunct — collapses the whole formula to `true`, having
determined `n = 5` and `m = 5` without ever searching either variable's sort.

That second application is the interesting part: a one-point *chain*, where
resolving one conjunct exposes another, needs the rule to be applied to a
fixpoint rather than once.

## Static

`merc_enumerate` applies exactly this fixpoint once per goal, before search
starts: split the (already-rewritten) body into its top-level `&&`-conjuncts,
repeatedly find one of shape `x == e` / `e == x` for a still-unbound `x`,
substitute, and re-split the residual. Running it to a fixpoint is what makes
the `n == 5 && m == n` chain above resolve in one pass: binding `n` first
turns the second conjunct into `m == 5`, a fresh one-point conjunct the same
loop picks up before returning. Whatever conjuncts remain afterwards are what
actually goes to search.

This is a *static* pass in the sense that it only ever looks once, at the
goal's body as originally split — it runs before search starts and does not
run again as search proceeds.

## Applying it dynamically

The static pass only sees the *original* body's top-level conjuncts. A
conjunct that only becomes `x == e` shaped *after* some other variable has
been bound by ordinary constructor expansion — because it was sitting inside
an `if` whose condition only just collapsed — is invisible to it. Take:

```
map goal: Nat # Nat -> Bool;
var n, m: Nat;
eqn goal(n, m) = (n < 2) && if(n == 0, m == 50, m == 60);
```

Nothing here is a top-level `x == e` conjunct — the `m == 50` / `m == 60`
branches are arguments of `if`, not conjuncts of the goal. So the static pass
leaves both `n` and `m` in the search. `n` gets bound by ordinary expansion
almost immediately (`n = 0` is its smallest constructor value), and *at that
point* the guard rewrites to the plain conjunct `m == 50` — a one-point
opportunity that has just appeared mid-search, one work-item expansion after
the goal was first split. Nothing revisits it: the search instead walks `m`
up from `0` one successor at a time until it happens to hit `50`.

Applying the one-point rule *dynamically* — re-splitting the body into
conjuncts after every work-item expansion, not just once up front — would
catch this: as soon as `n == 0` collapses the `if`, the residual `m == 50`
conjunct would be picked up the same way the static pass already picks up a
chain.

Measured directly with the [`InnermostRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.InnermostRewriter.html), counting rewrite calls — one
per branch the search actually expands:

| Goal | Rewrite calls to find the witness |
|---|---|
| the guard above, searched as written | **58** |
| the same guard with `n` already fixed to `0` (`if(0 == 0, m == 50, m == 60)`), so the exposed `m == 50` conjunct is one-point *from the start* | **1** |

Both numbers come from the real enumerator, not an estimate — the second
column is exactly what a dynamic one-point pass would achieve on this goal,
simulated by handing the enumerator the post-collapse goal directly instead
of implementing the re-scan.

### Why merc doesn't do this yet

The static fixpoint already resolves every conjunct-*chain* case for free
(the `n == 5 && m == n` example above), so a dynamic pass would only earn its
keep on the narrower "hidden behind a non-`&&` connective, exposed by an
unrelated variable's binding" pattern this page demonstrates. It also isn't
free: re-splitting a potentially large body into conjuncts on every queue pop,
instead of once per goal, is real per-step overhead that has to be paid on
*every* search, including the overwhelming majority that never hit this
pattern.

Tracked as deferred work in the enumeration crate's own plan in the `merc`
repository: worth implementing once a real specification's guards are shown
to hit this pattern often enough for the 57-call gap above to matter in
aggregate — not before.

The same static split has a second blind spot, independent of static vs.
dynamic. The one-point rule works from one conjunct split, which only
flattens top-level `&&`. A goal whose body is a top-level `||` — say
`∃x,y . (x == 1 && P(y)) || (x == 2 && Q(y))` — hides its per-disjunct
one-point conjuncts behind that `||`, and the search falls back to blind
joint enumeration of both disjuncts at once. Fixing it means splitting the
*goal* by quantifier polarity first (on `||` for `∃`, on `&&` for `∀`) and
running the preprocessing per branch, which turns a single body into a
worklist of sub-goals — a bigger structural change than the heuristic it
would improve.
