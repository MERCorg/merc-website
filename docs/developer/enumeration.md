# Data enumeration

## The one-point rule, and its dynamic gap

Closing a `sum`/`∃`/`∀` variable means picking concrete constructor values
until the guard decides. The cheapest possible case needs no search at all:
if the guard contains a conjunct `x == e` for a bound variable `x` and a term
`e` that doesn't mention it, `x` can only ever be `e` — bind it directly and
drop it from the search. This is the *one-point rule*, the degenerate,
single-step case of narrowing (no unifier to compute, just reading a
conjunct). Note that reading it off a *conjunct* is the existential form:
`∃x. x == e && φ(x)` is `φ(e)`, whereas the corresponding `∀` rule reads an
implication, `∀x. x == e ⟹ φ(x)`. Applying the conjunct form under a `∀`
narrows the domain to the single point `e` rather than preserving the
quantifier's meaning. mCRL2 ships it as a separate linearisation pre-pass
(`lps/one_point_rule_rewrite.h`); `merc_enumerate` applies it as part of the
enumerator's own goal preprocessing instead, so it also benefits `sum`
exploration and nested quantifiers, not just the LPS's top-level guard.

## What merc does today: a static pass

`merc_enumerate` runs the one-point rule once per goal, before search starts:
split the (already-rewritten) body into its top-level `&&`-conjuncts, repeatedly
find one of shape `x == e` / `e == x` for a still-unbound `x`, substitute, and
re-split the residual — a fixpoint, so a *chain* like

```
n == 5 && m == n
```

resolves in one pass: binding `n` first turns the second conjunct into
`m == 5`, itself a fresh one-point conjunct the same loop picks up before
returning.

## The gap: a one-point conjunct hidden behind `if`

The fixpoint only ever looks at the *original* body's top-level conjuncts. A
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

Measured directly (`merc_enumerate::Enumerator::find_witness`, `InnermostRewriter`,
counting calls to `rewrite_with` — one per branch the search actually
expands):

| Goal | `rewrite_with` calls to find the witness |
|---|---|
| the guard above, searched as written | **58** |
| the same guard with `n` already fixed to `0` (`if(0 == 0, m == 50, m == 60)`), so the exposed `m == 50` conjunct is one-point *from the start* | **1** |

Both numbers come from the real enumerator, not an estimate — the second
column is exactly what a *dynamic* one-point pass (re-splitting the body into
conjuncts after every work-item expansion, not just once up front) would
achieve on this goal, simulated by handing the enumerator the post-collapse
goal directly instead of implementing the re-scan.

## Why merc doesn't do this yet

The static fixpoint already resolves every conjunct-*chain* case for free
(the `n == 5 && m == n` example above), so a dynamic pass would only earn its
keep on the narrower "hidden behind a non-`&&` connective, exposed by an
unrelated variable's binding" pattern this page demonstrates. It also isn't
free: re-splitting a potentially large body into conjuncts on every queue pop,
instead of once per goal, is real per-step overhead that has to be paid on
*every* search, including the overwhelming majority that never hit this
pattern.

Tracked as deferred work in `docs/enumeration-crate-plan.md` (§6.3/§8.4,
Phase 5) in the `merc` repository: worth implementing once a real
specification's guards are shown to hit this pattern often enough for the
57-call gap above to matter in aggregate — not before.

The same static split has a second blind spot. Both the one-point rule and
the variable ordering below work from `split_conjuncts`, which only flattens
top-level `&&`. A goal whose body is a top-level `||` — say
`∃x,y . (x == 1 && P(y)) || (x == 2 && Q(y))` — hides its per-disjunct
one-point conjuncts behind that `||`, and the search falls back to blind
joint enumeration of both disjuncts at once. Fixing it means splitting the
*goal* by quantifier polarity first (on `||` for `∃`, on `&&` for `∀`) and
running the preprocessing per branch, which turns a single body into a
worklist of sub-goals — a bigger structural change than the heuristic it
would improve.

## Which variable to expand first

Once the one-point rule has taken out everything it can, whatever is left has
to be searched, and the order matters. `merc_enumerate` ranks the surviving
variables once per goal by, first, how many top-level conjuncts each one is
the *sole* remaining free variable of, then by raw mention count, with ties
broken by the caller's declaration order.

The sole-survivor rule is the useful half: binding a variable that is the
only unbound one left in a conjunct makes that conjunct ground immediately,
so the search's reject test can decide it and prune the branch one step
earlier than it otherwise would. Measured on a goal with one vacuous variable
and one directly-constrained variable, declared in the "wrong" order,
`find_witness` needs `max_items >= 18` with the ordering applied against
`>= 22` without it. Real, but modest — the ranking runs once per goal and
never re-ranks the fresh variables that a constructor expansion introduces
at each level, which are appended behind whatever was already queued.

Like the one-point pass, this is a static approximation: it counts how many
of the bound variables a conjunct still mentions, never what the conjunct
evaluates to.

## Bindings along a branch

The search is breadth-first, so many partially-instantiated branches are
outstanding at once, and each one extends a shared prefix of the bindings
chosen so far. Representing a branch's bindings as an owned map per work item
would copy that prefix on every expansion, so `merc_enumerate` keeps them as
a linked list of `(variable, value)` nodes in one arena owned by the
enumerator: extending a branch is a push, and every sibling that shares the
prefix stays valid. The arena is cleared, not dropped, between searches, so a
caller driving many searches through one enumerator — LPS `sum`-successor
generation is the motivating case — reuses its capacity.

A chain is deliberately *not* a general substitution. A variable's image may
mention variables bound later in the same chain (`v ↦ c(y1, y2)` where `y1`
and `y2` are fresh variables introduced to expand `v`), so splicing a chain
into a term with other free variables outstanding would leave them behind.
It is only used that way to normalise the search's own goal body, where the
enumerator knows exactly which variable is being replaced; resolving a
finished branch to ground values instead walks the chain recursively.

That resolution has to rewrite as it goes, not only at the leaves.
Substituting already-normal arguments into a constructor can still leave the
composite reducible — under the machine-word `Nat` encoding, `@succ_nat`
applied to a normalised digit still needs its carry-propagating equation to
fire — and the values handed back to a caller are spliced straight into
further `rewrite_with` calls as substitution images, which requires them to
be normal forms.

## Testing the enumerator against a second implementation

`merc_enumerate` ships a `NaiveEnumerator` alongside the real one, in the
same role `merc_sabre::NaiveRewriter` plays for the rewrite engines:
materialise every ground term of each variable's sort up to a size bound,
substitute all variables at once, rewrite once per combination. No
incremental normalisation, no pruning, no one-point rule, no fairness scheme
to get wrong. Random goals are then run through both and their solution
*sets* compared.

Two things make that suite cheap enough to run 200 goals per invocation.
Goals are built through the `merc_data`/`merc_sabre` API rather than
generated as source text, so neither the parser nor the typechecker runs per
goal. And the rewriters are built once, outside the loop: constructing an
`InnermostRewriter` compiles a `SetAutomaton` over every equation the
specification carries, which includes the whole lowered built-in library
(331 equations even for a specification declaring one small custom sort), so
rebuilding one per goal dominated the runtime of an earlier version of the
test — over a CPU-minute for 200 goals, against well under a second with the
rewriters shared. A real caller builds its rewriter once per run for exactly
the same reason.
