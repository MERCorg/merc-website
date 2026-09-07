# Condition caching

a condition cache is a bounded, LRU-evicting map from a condition side's
already-substituted term to its normal form, filled lazily as the computation
runs. It exists because checking a conditional rewrite rule's `if` clause can
end up normalising the *same* subterm more than once: two sibling rules whose
conditions disagree on the same computed value:

```
  odd(s(N)) -> true if even(N) = true
  odd(s(N)) -> false if even(N) = false
```

Or a rule's condition getting re-checked, on the same concrete argument, from
several unrelated call sites of a deep recursion (`evalexpr.rec`'s `succ17`, see
below). Without a cache, a specification whose conditions are cheap on their own
can still blow up combinatorially once those conditions are checked repeatedly
this way — oddeven.rec is the sharpest example: `2^(n+1)-1` rewrite steps
uncached versus `n+1` cached.

Both engines carry a cache unconditionally now (`::new` picks a default
capacity; `::with_condition_cache_capacity` picks another). Since the key is
the *substituted* term rather than any rule's unsubstituted pattern, which
variable name a rule happens to bind an argument to never enters into the
lookup at all — `merc_aterm`'s maximal sharing means two structurally equal
substituted terms are the same interned value (structural equality is
pointer equality), so two entirely unrelated rules that happen to compute
the same concrete subterm still share the cache entry.

## Static caching

`evalexpr.rec`'s `succ17` — successor on a 17-bit bounded natural, wrapping
back to `Z` at the bound — is a sibling-conditioned rule:

```
succ17(r) -> Z    if eq(r, S(S(...16 S's...(Z)))) = true
succ17(r) -> S(r) if eq(r, S(S(...16 S's...(Z)))) = false
```

Both rules share the same left-hand side and the same condition subterm
`eq(r, S^16(Z))` — a *static* per-rule (or sibling-group) cache finds this
one on its own: when the first rule's condition fails, the second rule's
identical check reuses the already-computed result instead of recomputing
it, no dynamic cache required.

What a static cache cannot see is how many *different, unrelated* places in
the specification end up asking `succ17` that same question. `plus17`,
`mult17` and `exp17` all recurse through `succ17`:

```
plus17(r, S(t)) -> succ17(plus17(r, t))
mult17(r, S(t)) -> plus17(r, mult17(r, t))
exp17(r, S(t))  -> mult17(r, exp17(r, t))
```

and `eval17` — which recursively evaluates an arithmetic expression tree —
calls into all three, plus itself, at every node:

```
eval17(Exs(n))     -> succ17(eval17(n))
eval17(Explus(n,m)) -> plus17(eval17(n), eval17(m))
eval17(Exmult(n,m)) -> mult17(eval17(n), eval17(m))
eval17(Exexp(n,m))  -> exp17(eval17(n), eval17(m))
```

The spec's actual EVAL goal, `lambda0(m) -> eq(eval17(m), evalexp17(m))`
(with `evalexp17(n) -> eval17(expand(n))`), then runs two structurally
different evaluations of related expressions side by side. Across that
whole computation, `succ17`'s condition ends up being checked on the same
concrete `SNat` value from many separate, structurally unrelated call
sites — not from two rules announced at the same match, which is the only
shape a static analysis of the rule set could ever predict ahead of time,
since it depends on which concrete numbers a particular run actually
produces, not on how the rules are written. Measured: `InnermostRewriter`
with only the (removed) static cache took 19,698,985 rewrite steps on
evalexpr.rec's EVAL terms; with the dynamic cache, 8,265,493 — well under
half, all from catching exactly this pattern.

## Scope: condition sides only

The cache is only consulted where a condition side is normalised, not during
ordinary matching. Two rules `f(c) -> a` and `g(c) -> b`, called on the same
expensive-to-normalise `c` with no condition in sight (e.g. `h(f(c), g(c))`),
still normalise `c` twice — that is matching-argument sharing, a different
problem from condition-side sharing. 

```
f(x) -> a if x = c
g(y) -> b if y = c
```

by contrast — `c` inside *two different rules' own conditions* rather than
their arguments — the cache does reach: whichever of the two is checked second
reuses the first's already-normalised `c`, the same way it reuses `succ17`'s
already-checked condition above, regardless of the rules being otherwise
unrelated.

## A real limitation: nested occurrences within one condition side

The cache is keyed on the result of evaluating one condition side's pattern
*as a whole* — it is only ever consulted once per side, not once per
subterm within that side. So `not(E) = true` and `E = true` — `E` nested
inside the first condition's pattern, but the *entirety* of the second's —
do **not** share `E`'s computation: the first condition's cache entry is
keyed on the whole `not(E)`, never on `E` alone, so the second condition's
lookup on bare `E` misses and recomputes it from scratch.

Measured directly with a synthetic `slow(x)` spec of exactly this shape
(`slow` takes `n` steps to normalise): `not(slow(x)) = true` alongside
`slow(x) = true` takes 403 steps (`slow(x)` computed twice); both
conditions written as `slow(x)` in full (no nesting) takes 201 (computed
once, one cache hit).

The *removed* static per-rule cache did not have this gap, but did slow down
overall rewriting because it had to maintain and check a more complex cache
structure for every subterm of every condition side.
