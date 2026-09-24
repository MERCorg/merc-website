# Constraint Generation & the Solver

`crates/typecheck/src/inference/inference.rs` is the per-equation driver
built on top of [the `Unifier`](unification.md). It runs in two stages:
[`ConstraintGenerator`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.ConstraintGenerator.html) walks the AST once and emits a flat list of
[`Constraint`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html)s, then [`Solver`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.Solver.html) backtracks over that list, calling into
the `Unifier` at every choice point and keeping the single best leaf it
reaches.

## Top-level shape

```
infer(roots, declared_scope):
    unifier = Unifier::new()
    for (var, sort) in declared_scope:
        declared_sorts[var] = unifier.resolved_node(sort)

    expr_id_of = number_expr_nodes(roots)                   -- stable id per AST node
    expr_sorts = [unifier.fresh_var() for _ in expr_id_of]  -- one hole per node, up front

    generator = ConstraintGenerator { unifier, declared_sorts, expr_sorts, constraints: [], ... }
    generator.generate(roots)                                -- fills `constraints`; may unify eagerly

    constraints = merge_shared_subs(generator.constraints)   -- grouped Subs -> one Join each

    solver = Solver { unifier, constraints, expr_sorts, best: None,
                       default_sort: underdetermined_default_sort(role) }
    solver.solve(0)

    match solver.best:
        None                     -> Err(NoTyping)
        Some { duplicate: true } -> Err(AmbiguousExpression)  -- two leaves tied at the minimum measure
        Some { typing: Some(sorts, names) } -> Ok(EquationTyping { sorts, names, ... })
```

Every expression node — condition, left- and right-hand side of an equation,
or a single standalone expression — gets an [`ExprId`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/type.ExprId.html) assigned up front by
[`number_expr_nodes`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/fn.number_expr_nodes.html), in a fixed traversal order (parents before
children; an application's **arguments before its function**). `expr_sorts`
is pre-filled with one fresh unification variable per id before generation
even starts, so the generator's `visit` never mints a sort node itself — it
only looks one up by id. The argument-before-callee ordering is what makes
the search tractable: by the time the generator (and later the solver)
reaches a callee's overload choice, the argument holes are usually already
bound to something concrete, so most overloads fail to unify on the first
try.

## Constraint generation

[`ConstraintGenerator::visit`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.ConstraintGenerator.html#method.visit) recurses over the lowered expression tree and,
per node, either unifies eagerly (a structural fact that must hold in *every*
solution — a callee having a function sort, a condition being boolean — is
enforced immediately, so a violation is a direct error, not a silent search
failure) or pushes one [`Constraint`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html):

| Constraint | Fields | Meaning |
|---|---|---|
| [`Sub`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Sub) | `lhs, rhs: InferSortId` | `lhs` must be a subsort of `rhs` (an implicit up-cast) |
| [`Lit`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Lit) | `sort: InferSortId, kind: LitKind` | a numeric literal's sort must admit its kind (`Positive` or `Natural`; `0` can't be `Pos`) |
| [`Disjunction`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Disjunction) | `expr: ExprId, sort: InferSortId, disjuncts: [(NameTarget, InferSortId)]` | a name with several candidate overloads; the solver commits to exactly one |
| [`Comprehension`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Comprehension) | `body, node: InferSortId, element: ResolvedSortId` | `{x: S \| e}` reads as `Set(S)` (boolean body) or `Bag(S)` (numeric body) |
| [`Join`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Join) | `sources: [InferSortId], target: InferSortId` | the lattice least-upper-bound of several branches sharing one target |

Constraints are solved **in generation order**, not grouped by kind — this is
what makes "arguments before callee" actually pay off, since a `Disjunction`
for the callee is generated (and therefore solved) after the `Sub`/`Lit`
constraints for its already-visited arguments.

### Building a `Disjunction`: name resolution

[`gen_name`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.ConstraintGenerator.html#method.gen_name) resolves one `Id` occurrence. A declared variable (an
equation's own `var`, a binder, a process parameter) is looked up in
`declared_sorts` and bound to the node directly — no constraint needed, since
there is only one possible target. Otherwise
[`push_signature_disjuncts`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.ConstraintGenerator.html#method.push_signature_disjuncts) collects every candidate from the
[`Signature`](https://mercorg.github.io/merc/merc_typecheck/struct.Signature.html): each matching constructor/mapping overload becomes a
[`NameTarget::Op`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.NameTarget.html#variant.Op) disjunct with its own ground sort, and each matching
*scheme* (`==`, `<`, `if`, the polymorphic container operations, …) is
instantiated fresh via
[`instantiate_scheme`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.ConstraintGenerator.html#method.instantiate_scheme) — every
[`ResolvedSort::TypeVar`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.TypeVar) it mentions becomes one fresh unification
variable, shared between all of that instantiation's occurrences, which is
what lets `in: S # List(S) -> Bool` mean "the same `S`" on both sides at one
particular call site. Zero candidates is an [`UndeclaredName`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.InferenceError.html#variant.UndeclaredName) error;
exactly one is bound directly, like a variable; more than one becomes a
[`Disjunction`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Disjunction) constraint, to be resolved later by the solver, not here.

There is no dedicated constraint kind for arithmetic operators — `+`, `-`,
`*`, `div`, `mod` and the rest are ordinary overloaded mappings declared in
`pos.mcrl2`/`nat.mcrl2`/`int.mcrl2`/`real.mcrl2`, so an application of one
goes through exactly this same `Disjunction` machinery.

### `merge_shared_subs`: from `Sub` groups to `Join`

Several `Sub` constraints can target the *same* shared free variable — the
two operands of `==`, the branches of an `if`, a set/bag element, an
equation's LHS and RHS. Solving them as independent, sequential `Sub`s is
order-sensitive: whichever source is solved first binds the shared variable
by equality, so if a finite-container source (a set literal, fixing `FSet`)
is solved before another source that only admits `Set`, the second source's
own `Sub` then fails and forces a fruitless re-exploration.
[`merge_shared_subs`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/fn.merge_shared_subs.html) runs once, right after generation, and groups every
`Sub` by the union-find root of its target: a group of two or more collapses
into a single [`Join`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Join), at the position of the group's last
member, computing the least common supersort of all sources in one step
instead. A disjunction's own candidate parameters are *distinct* fresh
variables per overload (the overload isn't committed to yet), so they are
never grouped this way.

## The solver

```
struct Solver:
    unifier, constraints, expr_sorts, base_names      -- inputs, shared for the whole search
    choices: [(ExprId, NameTarget)]                    -- disjunct picked per Disjunction, on the current branch
    measure: [u8]                                      -- measure components pushed on the current branch
    best: Option<Candidate>                             -- best leaf found so far
    default_sort: ResolvedSortId                        -- substituted for a hole still free at a leaf
```

```
solve(index):
    if dominated(): return false        -- branch-and-bound: this branch's measure prefix already loses
    constraint = constraints[index] or None
    match constraint:
        None                  -> leaf(); return true         -- end of the list: score this solution
        Disjunction(d)        -> solve_disjunction(d, index)
        Sub(s)                -> solve_widening(s.lhs, s.rhs, |slf| slf.solve(index + 1))
        Lit(l)                -> solve_lit(l, index)
        Comprehension(c)      -> solve_comprehension(c, index)
        Join(j)                -> solve_join(j, index)
```

### Branch-and-bound: `dominated`

```
dominated():
    match best:
        None       -> false
        Some(best) -> measure > best.measure[..measure.len()]   -- component-wise, so-far prefix only
```

A `Disjunction`/`Comprehension` contributes no measure component of its own
(every alternative is tried regardless, so a tie is still detected as
ambiguity), so without this check an equation with several independent
overloaded operators would explore every *combination* to a full leaf even
after a strictly better solution is already known — exponential in the
number of disjunctions. The pruning is exact, not a heuristic: because
earlier measure components dominate the lexicographic order, a prefix that
is already strictly worse can never catch up, so this changes only how much
of the tree gets visited, never which typing wins.

### Exhaustive choice points: `solve_disjunction`, `solve_comprehension`

```
solve_disjunction(d, index):
    found = false
    for (target, sort) in d.disjuncts:
        snapshot = unifier.snapshot()
        if unifier.unify(d.sort, sort):
            choices.push((d.expr, target))
            found |= solve(index + 1)
            choices.pop()
        unifier.rollback_to(snapshot)
    return found
```

`solve_comprehension` has the same shape over exactly three fixed readings —
`(Bool, Set)`, `(Nat, Bag)`, `(Pos, Bag)` — unifying both the body sort and
the comprehension node's own sort against each reading in turn. Both
functions try **every** alternative unconditionally (no early return on
success) precisely so that two alternatives reaching equal-measure leaves are
both recorded and detected as a tie by `leaf`, rather than the first success
silently shadowing the second.

### Subsorting: `solve_sub` / `solve_widening`

```
solve_widening(lhs, rhs, continue_with):
    snapshot = unifier.snapshot()
    if unifier.unify(lhs, rhs):                 -- try equality first
        measure.push(0)
        found = continue_with(self)
        measure.pop()
    unifier.rollback_to(snapshot)
    if found: return true

    pairs = unifier.strict_super_sorts(lhs).map(wider => (wider, rhs))
         or unifier.strict_sub_sorts(rhs).map(narrower => (lhs, narrower))
         or return false                         -- neither side has an enumerable shape

    for (distance, (lhs, rhs)) in pairs.enumerate():   -- nearest widening first
        snapshot = unifier.snapshot()
        if unifier.unify(lhs, rhs):
            measure.push(1 + distance)
            found = continue_with(self)
            measure.pop()
        unifier.rollback_to(snapshot)
        if found: return true
    return false
```

`solve_widening` is shared by `solve_sub` (a plain `Sub` constraint) and, as
a fallback, by the `Join` path below. It takes the **first** success only —
equality if it works, otherwise the nearest strict widening that works — and
stops there, never comparing alternative widening distances against each
other directly. That is enough to guarantee the minimal upcast wins:
distances are tried in ascending order, and `continue_with` recurses into the
*rest* of the constraint list before this function returns, so a later
constraint failing under a near widening still gets to retry under a farther
one — the "first success" is first-success-of-the-whole-remaining-search, not
just of this one constraint in isolation.

### Literals: `solve_lit`

A literal's sort is either already resolved (check its `generality` admits
the literal's kind, e.g. reject `Pos` for a literal that must be `Natural`
like `0`, push that generality as the measure) or still a hole, in which case
the solver tries each admissible number sort **most specific first** —
`[Pos, Nat, Int, Real]` for a `Positive` literal, `[Nat, Int, Real]` for a
`Natural` one — unifying, pushing that sort's generality as the measure
component, recursing, and rolling back on failure, same snapshot/try/rollback
shape as everything else.

### The lattice join: `solve_join` / `solve_join_seq`

```
solve_join(j, index):
    resolved = [unifier.resolve(source) for source in j.sources]
    if any source unresolved: return solve_join_seq(j.sources, j.target, 0, index)   -- fallback

    lub = resolved[0]
    for next in resolved[1..]:
        lub = sorts.join(lub, next) or return solve_join_seq(...)  -- not joinable by the simple lattice

    if not every resolved source is materializable into lub:
        return solve_join_seq(...)                                 -- join reaches a sort lowering can't build yet

    if not unifier.unify(j.target, resolved_node(lub)): return false
    for source in resolved:
        measure.push(widening_distance(source, lub).head)          -- one component per source, matching solve_sub
    found = solve(index + 1)
    pop all pushed components
    return found

solve_join_seq(sources, target, i, index):     -- the pre-merge two-Sub behavior, as a fallback
    if i == sources.len(): return solve(index + 1)
    return solve_widening(sources[i], target, |slf| slf.solve_join_seq(sources, target, i + 1, index))
```

The fast path only fires when every source is already fully resolved *and*
pairwise joinable *and* the join's result is one lowering can actually
materialize (container-element covariance and function contravariance are
relations the lattice can compute but Phase 4 lowering cannot yet build
coercions for); otherwise it defers to `solve_join_seq`, which reproduces
exactly the order-sensitive per-source widening the pre-`merge_shared_subs`
encoding used — so the rare underdetermined case (e.g. joining two still-open
empty containers) behaves identically to before that optimization existed.

### Scoring and extracting: `leaf` / `extract`

```
leaf():
    match (measure, best):
        no best yet, or measure < best.measure -> best = extract()          -- strictly better
        measure == best.measure                 -> best.duplicate = true    -- tie: ambiguous
        measure > best.measure                  -> discard                  -- (unreachable: dominated() would have pruned)
```

```
extract():                                      -- reads bindings before backtracking destroys them
    sorts = [unifier.resolve_or_default(node, default_sort) for node in expr_sorts]
    names = base_names ++ choices                -- every Disjunction's committed NameTarget, overlaid
    return Candidate { measure, duplicate: false, typing: Some((sorts, names)) }
```

`extract` runs **before** the caller unwinds back through the `snapshot`s
that led to this leaf, since those bindings are exactly what it's reading.
Every free node still unbound at this point (a hole nothing ever
constrained, like the element sort of a never-observed empty container)
resolves to `default_sort` instead of `None` — see
[`Unifier::resolve_or_default`](unification.md#resolving-a-solved-node). That default is
computed once per equation, before solving starts, by
[`underdetermined_default_sort`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/fn.underdetermined_default_sort.html): ordinarily `Bool` — an arbitrary
but harmless choice, since a node that reaches this path is by definition
never observed by any other constraint — except when checking one Appendix-B
template's own equations with exactly one declared `type_var`, where
defaulting to `Bool` would be actively wrong: a bare literal like the `{}` in
`#({}) = @c0` has no `var`-declared occurrence to unify its element sort
against, so it would *always* solve to `Bool` regardless of which concrete
sort the template later gets instantiated for. Defaulting to the template's
own type variable instead keeps such a literal polymorphic through checking,
exactly like a declared occurrence would be, so specialization substitutes it
correctly.

## Worked example: an eagerly-bound argument pruning a disjunct

```mcrl2
map  f: Nat -> Nat;
     f: Int -> Int;
var  n: Nat;
eqn  f(n) = n;
```

Generation visits the argument `n` before the callee `f` (argument-before-
function ordering), binding `n`'s node directly to `Nat` — it's a declared
variable, not a disjunction. `f`'s occurrence then becomes a two-way
[`Disjunction`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Disjunction). Solving it:

- **`f: Nat -> Nat`** — unifying the parameter against the argument node
  (already `Nat`) succeeds by equality; the `Sub` constraint linking them
  contributes measure `0`.
- **`f: Int -> Int`** — the argument is `Nat`, the parameter wants `Int`;
  equality fails, `solve_widening` falls through to `strict_super_sorts(Nat)`
  = `[Int, Real]`, and the nearest, `Int`, succeeds at distance `1`.

Both branches reach a leaf — the call type-checks either way — but their
measures differ at that one component: `[…, 0, …]` beats `[…, 1, …]`, so
`Nat -> Nat` is the unique best solution and no `AmbiguousExpression` is
raised. This is the concrete mechanism behind the informal rule "the exact
overload wins over one that needs an up-cast": nothing in `unify` itself
prefers one branch over the other, it's `leaf`'s lexicographic comparison of
`Solver::measure` that does.
