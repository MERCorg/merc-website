# The Unifier

[`Unifier`](https://mercorg.github.io/merc/merc_typecheck/inference/unification/struct.Unifier.html) (`crates/typecheck/src/inference/unification.rs`) solves sort
equality by structural unification over a union-find table, backed by
[`ena`](https://crates.io/crates/ena) — the same crate the Rust compiler's own
type inference uses. It is a single-purpose component: given two sort
expressions that may still contain holes, decide whether they can be made
equal, and if so, make them so. It has no notion of equations, overloads, or
ranking — that all lives one level up, in [the solver](solver.md).

## Data model

A sort under inference is either fully known or still has holes in it — the
element sort of an empty list literal, for instance, before anything
constrains it. The `Unifier` represents such a sort as a node in an
append-only arena:

```
InferSortId = an index into Unifier.arena

InferSort =
  | Resolved(id)                     -- a fully known, interned sort (Nat, Bool, ...)
  | Generic { op, subsort }          -- List(x), Set(x), Bag(x), ... where x may still be a hole
  | Function { domain: [x], range }  -- d1 # d2 # ... -> r, any part of which may still be a hole
  | Var(SortVar)                     -- a hole, pointing into the union-find table
```

There are two distinct identities in play, easy to conflate:

- an [`InferSortId`](https://mercorg.github.io/merc/merc_typecheck/inference/unification/type.InferSortId.html) is just "a node in the arena" — **structural**, not
  deduplicated. Two different ids can denote the same sort (e.g. two
  occurrences of `List(?t)` built independently), and only [`unify`](https://mercorg.github.io/merc/merc_typecheck/inference/unification/struct.Unifier.html#method.unify) decides
  whether they are semantically equal.
- a [`SortVar`](https://mercorg.github.io/merc/merc_typecheck/inference/unification/struct.SortVar.html) is a union-find key. It is what [`InferSort::Var`](https://mercorg.github.io/merc/merc_typecheck/inference/unification/enum.InferSort.html#variant.Var) wraps, and
  it is the only thing [`snapshot`](https://mercorg.github.io/merc/merc_typecheck/inference/unification/struct.Unifier.html#method.snapshot)/[`rollback_to`](https://mercorg.github.io/merc/merc_typecheck/inference/unification/struct.Unifier.html#method.rollback_to) checkpoint.

`resolved_node` memoizes `Resolved(id) -> InferSortId` in a side table, so
repeated references to the same already-known sort (e.g. re-fetching `Nat`
for every argument of `+`) share one arena node rather than allocating a
fresh one each time.

## Unification

```
shallow_normalize(id):
    while arena[id] is Var(v) and table.probe(v) is bound to `next`:
        id = next                      -- follow the binding chain
    return id                          -- either non-Var, or an unbound Var

unify(lhs, rhs):
    lhs = shallow_normalize(lhs); rhs = shallow_normalize(rhs)
    if lhs == rhs: return true
    match (arena[lhs], arena[rhs]):
        (Var, Var)          -> merge the two union-find classes              -- always succeeds
        (Var v, other)      -> bind(v, other)
        (other, Var v)      -> bind(v, other)
        (Resolved a, Resolved b)        -> a == b                            -- interning: one integer compare
        (Resolved r, Generic{op, sub})  -> op matches r's constructor, then unify(sub, r's element)
        (Resolved r, Function{dom,rng}) -> arity matches, then unify each domain pair and unify(rng, r's range)
        (Generic a, Generic b)          -> a.op == b.op and unify(a.subsort, b.subsort)
        (Function a, Function b)        -> equal arity and unify all domain pairs and unify(a.range, b.range)
        _ -> false                                                           -- shape mismatch

bind(var, value):
    if occurs(var, value): return false   -- reject ?t := List(?t)
    table.unify_var_value(var, Some(value))
    return true
```

Two things make this cheaper than a naive structural unifier:

- **Interning collapses the base case.** Two [`Resolved`](https://mercorg.github.io/merc/merc_typecheck/inference/unification/enum.InferSort.html#variant.Resolved) leaves unify by
  comparing their interned ids — no recursion needed even for a deeply
  nested sort, as long as neither side still has a hole in it.
- **A resolved sort unifies directly against a spelled-out one.** A
  half-known `Generic{List, ?t}` (an empty list literal) unifies against the
  fully resolved `List(Nat)` by looking up `List(Nat)`'s element sort in the
  interner and unifying `?t` against it — the resolved side never needs to be
  "expanded" into its own arena nodes up front.

`unify_values` (the [`UnifyValue`](https://docs.rs/ena/latest/ena/unify/trait.UnifyValue.html) impl backing `bind`'s merge) asserts that at
most one side of a merge is ever already bound — `unify`'s `(Var, Var)` arm
only merges two variables while *both* are still unbound, since two already-
bound classes are unified **structurally** first (recursing into their
values), never merged wholesale. That is what makes transitive merging safe:
`?a = ?b` merges two holes; a later `?b := Bool` binds the merged class, and
resolving `?a` afterwards follows the merge to find `Bool`.

### The occurs check

`bind` refuses a binding that would create an infinite sort:

```
occurs(var, id):
    id = shallow_normalize(id)
    match arena[id]:
        Var(other)          -> table.unioned(var, other)     -- same union-find class?
        Resolved(_)          -> false
        Generic{subsort}     -> occurs(var, subsort)
        Function{domain,range} -> any(occurs(var, d) for d in domain) or occurs(var, range)
```

`?t := List(?t)` is rejected directly; so is `?t := List(?a)` after `?t` and
`?a` have separately been merged into the same class — `occurs` follows
`table.unioned`, not pointer identity, so a cycle introduced indirectly
through a prior merge is caught too.

## Resolving a solved node

```
resolve(id):                              -- None if a hole remains anywhere inside
    id = shallow_normalize(id)
    match arena[id]:
        Var                 -> None
        Resolved(r)          -> Some(r)
        Generic{op,subsort}  -> resolve(subsort).map(s => interner.generic(op, s))
        Function{domain,range} -> resolve every domain entry and range, or None if any is None
```

`resolve_or_default(id, default)` is the same walk, substituting `default`
for a `Var` instead of failing. It exists because a leaf of the solver's
search can legitimately leave a hole unconstrained — the element sort of `#[]`
in an equation that never observes the empty list's contents, for instance —
and such an equation should still type check rather than be rejected as
underdetermined. What `default` actually is isn't fixed inside the `Unifier`;
it is computed once per equation by
[`underdetermined_default_sort`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/fn.underdetermined_default_sort.html) and threaded in — see
[the solver page](solver.md#scoring-and-extracting-leaf-extract) for when and why it
differs from the usual `Bool`.

## The subsort lattice

Unification only ever decides **equality**. The strict-subsort ordering
(`Pos <: Nat <: Int <: Real`, `FSet <: Set`, `FBag <: Bag`) is exposed
separately, as an enumeration the solver walks explicitly when a plain
equality does not hold:

```
strict_super_sorts(id):    -- None for a still-unbound Var, whose shape isn't known yet
    match arena[normalize(id)]:
        Resolved(Primitive(s)) -> the number sorts strictly above s, nearest first
                                    (e.g. Pos -> [Nat, Int, Real])
        Resolved(Container{op, sub}) -> [the wider constructor applied to sub], if op has one
                                          (e.g. FSet(x) -> [Set(x)])
        Generic{op, sub}        -> same container widening, without resolving sub
        Function                -> []                                    -- functions never widen
        _                       -> []

strict_sub_sorts(id): the mirror image (Real -> [Int, Nat, Pos], Set(x) -> [FSet(x)])
```

Only the **head constructor** widens: `List(Nat)` itself has no supersorts
even though `Nat` does — the numeric chain and the finite/infinite container
pairing are the only two widenings the language defines, and neither reaches
inside a container's element. This is exactly `number_generality`'s table
(`Pos = 0, Nat = 1, Int = 2, Real = 3`) read in each direction, plus the two
hard-coded container pairs (`FSet <: Set`, `FBag <: Bag`).

## Snapshot and rollback

```
snapshot():  return table.snapshot()          -- ONLY the union-find bindings
rollback_to(s): table.rollback_to(s.snapshot) -- undoes bindings made since `s`
```

This is the entire backtracking contract the solver relies on for every
disjunct, comprehension reading, and widening attempt it tries and discards.
Crucially, it checkpoints **only** `table` — the union-find bindings. The
`arena` is append-only and is never part of a snapshot: any node pushed by
`generic`, `function`, `resolved_node`, or `fresh_var` while a branch that
later gets rolled back was being explored simply stays in the `Vec` forever,
unreachable but not freed.

This is deliberate, not an oversight — the struct's own doc comment calls it
out as "harmless garbage" — and it is harmless because of *scope*, not
because the arena is somehow reclaimed: [`infer`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/fn.infer.html) constructs a fresh
`Unifier` as a plain local for each equation (or standalone expression) it
type checks, and drops it — arena included — the moment that one equation is
done. So the garbage from a large overload-resolution search never outlives
the equation that produced it, and never accumulates across a module or a
whole specification; a `debug_assert` in `rollback_to` additionally checks
that no *variable* is created between a `snapshot()` and its matching
`rollback_to()` (which would be lost by the checkpoint the same way), so the
only thing rollback is ever asked to leave behind is arena structure, never a
dangling table entry.

## Worked examples

**Binding a hole to a container, structurally.** Typing `n = #[]` against an
expected `List(Pos)`: the literal starts as `Generic{List, ?t}` for a fresh
`?t`; the expected sort is the resolved leaf `List(Pos)`.

```
resolved   = resolved_node(List(Pos))            -- Resolved(List(Pos))
structural = generic(List, fresh_var())          -- Generic{List, ?t}
unify(resolved, structural)
  -> Resolved vs Generic: List(Pos)'s element is Pos
  -> unify(resolved_node(Pos), ?t)
  -> Var case: bind(?t, Pos)
resolve(structural) == Some(List(Pos))
```

**Transitive merging.** `?a` and `?b` are unified while both are still
unbound (a pure merge, no structure touched); `?b` is bound to `Bool`
afterwards. `resolve(?a)` follows the merged class to `?b`'s binding and
returns `Some(Bool)` — this is the mechanism behind a scheme like
`==: S # S -> Bool`, where both operands share one type variable `S` before
either side's own sort is known.

**Occurs check.** `?t` unified against `List(?t)`: `bind` calls
`occurs(?t, List(?t))`, which recurses into the list's element and finds `?t`
again — rejected. The same rejection fires through an indirect merge: `?a`
and `?alias` merged first, then `?a` unified against `List(?alias)`, is
caught the same way because `occurs` checks union-find class membership, not
just direct equality.
