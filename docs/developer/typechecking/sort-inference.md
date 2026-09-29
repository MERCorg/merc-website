```math_preamble

\usepackage{tikz}
```
# Phase 5: Sort Inference

Given a fully desugared equation and a [signature](signature.md) to resolve
names against, it decides the sort of every sub-expression, choosing between
overloaded operators and inserting the implicit coercions the surface language
leaves out. This page covers the algorithm at the level of *what* it computes
and *why* it is correct; see [Solver](inference/solver.md) for
*how* it is implemented — a function-by-function walkthrough with
pseudocode, which this page links to throughout rather than duplicating. It
runs **per equation**, as a memoized query, in two steps — constraint
generation, then a ranked backtracking search — both introduced below.

## The sort lattice

Sort inference works over an interned lattice of *resolved* sorts, which is
the vocabulary shared by unification and the solver. A [`ResolvedSort`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html) is one
of:

- a [primitive](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.Primitive) sort (`Bool`, `Pos`, `Nat`, `Int`, `Real`);
- a [container](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.Container) sort `op(S)` such as `List(S)`, `Set(S)` or `FBag(S)`;
- a [function](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.Function) sort $A_0 \# \dots \# A_n \to B$;
- a nominal sort [`Def(d)`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.Def), identified by the declaration `d` it resolves to;
- a [`Unit`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.Unit) sort, used internally for the result of an action;
- a bound type variable [`TypeVar(v)`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.TypeVar), identified by the `type_var` declaration
  `v` it resolves to.

Because sorts are **interned**, each distinct sort is stored once and two
sorts are equal exactly when their indices are equal — a sort comparison is a
single integer comparison. Sub-sorts are stored as indices too, so a
[`ResolvedSort`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html) is small and structural equality never has to recurse.

These sorts form a **lattice** under a sub-sort ordering that follows the
mCRL2 book's own subtyping relation (Definition 15.1.8):

- the number sorts form a chain $Pos \leq Nat \leq Int \leq Real$;
- the finite containers embed into their unbounded counterparts,
  $FSet(S) \leq Set(S)$ and $FBag(S) \leq Bag(S)$;
- container sorts are **covariant** in their element: $op(S) \leq op(T)$
  whenever $S \leq T$, for any container constructor `op`, and the two steps
  above compose — $FSet(Pos) \leq Set(Nat)$ combines the finiteness step with
  the element widening;
- function sorts are **contravariant** in their domain and **covariant** in
  their range, e.g. $(Nat \to Int) \leq (Pos \to Real)$;
- all other distinct sorts are incomparable.

The lattice supplies a **join** (least common supersort) and **meet**
(greatest common subsort) over this ordering. A join is what lets two
branches of an `if`, or the two sides of an equation, meet at a single common
sort: joining `Nat` and `Int` yields `Int`, and joining `FSet(Pos)` and
`Set(Pos)` yields `Set(Pos)`.

Not every step in this ordering has a coercion that can actually build the
wider term, though. Only a sub-relation of it is
[**materializable**](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/struct.SortInterner.html#method.is_materializable):
the number chain, and the FSet/Set and FBag/Bag finiteness step when the
element sorts are already equal — exactly the coercions the surface language
inserts silently. Element-wise container covariance ($List(Pos) \leq
List(Nat)$) and function-sort variance are genuine entries in the sub-sort
order — the book's laws hold for them, and they let a `partial_cmp` or a
`join`/`meet` succeed — but there is no elementwise traversal, nor a
function-value coercion, that can materialize them into an actual term. The
solver's widening search (see below) only ever enumerates materializable
moves, so an equation that would need one of these wider steps is rejected
rather than accepted with a phantom coercion; `join` and `meet` operate over
the full ordering but fall back to solving each source independently when
their result turns out not to be materializable.

## Constraint generation

The generator walks the lowered condition, left-hand side and right-hand side
of one equation and, for every sub-expression, allocates a *sort node* in the
unifier (see below) and emits constraints relating those nodes. Nodes are
numbered by an [`ExprId`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/type.ExprId.html) in a fixed order — parents before children, and within
an application the **arguments before the applied function**. This ordering
matters: by the time the solver reaches a function's overload choice, the
argument sorts are already known, so most overloads can be rejected
immediately.

The constraint kinds are:

- **[Sub](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Sub)** — the sort of one node must be a sub-sort of another, modelling an
  implicit up-cast (a `Nat` argument passed where `Int` is expected). Equality
  is the special case where no coercion is needed.
- **[Lit](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Lit)** — a number literal must take a number sort admitting its kind (`0`
  is a natural, every other literal is positive). Literals prefer the most
  specific sort, so `1` is a `Pos` before it is widened.
- **[Disjunction](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Disjunction)** — a name with several overloads must resolve to exactly one
  of them. The solver commits to one disjunct per solution.
- **[Comprehension](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Comprehension)** — a set/bag comprehension `{ x: S | e }` reads as a
  `Set(S)` when its body is boolean and as a `Bag(S)` when its body is a
  number; the reading follows from the solved body sort.
- **[Join](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Join)** — a group of [`Sub`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Sub) constraints that all widen into the *same*
  shared sort variable (the operands of a comparison, the branches of an
  `if`, a set or bag element, the equation's two sides) is folded into one
  least-upper-bound over the lattice, rather than solved one [`Sub`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Sub) at a
  time — see
  [`merge_shared_subs`](inference/solver.md#merge_shared_subs-from-sub-groups-to-join)
  for why solving them independently would be order-sensitive.

There is no dedicated constraint kind for arithmetic operators — `+`, `-`,
`*`, `div`, `mod` and the rest are ordinary overloaded `map` names, declared
by `pos.mcrl2`, `nat.mcrl2`, `int.mcrl2` and `real.mcrl2` as part of
`system`'s own signature the same way a user's own overloaded mapping would,
so an application of one is typed through the ordinary
**[Disjunction](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Disjunction)** constraint above — exactly like [the worked
example in Inference
Internals](inference/solver.md#worked-example-an-eagerly-bound-argument-pruning-a-disjunct)
shows for a user-defined `f`.

Structural facts that must hold in *every* solution — that a callee has a
function sort, that a condition is boolean — are unified eagerly at
generation time, so a violation is reported as a direct error rather than a
silent search failure.

A bare product is not a valid variable sort at all — a binder declaring one is
rejected as
[`InferenceError::InvalidBinderSort`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.InferenceError.html#variant.InvalidBinderSort),
rather than left untyped and silently letting an ill-typed body slip through
unchecked.

## Unification with subtyping

Equality of sorts is decided by structural **unification** over a union-find
table, implemented by the
[`Unifier`](https://mercorg.github.io/merc/merc_typecheck/inference/unification/struct.Unifier.html).
See [The Unifier](inference/unification.md) for its data model (how a
half-known sort like `List(?t)` is represented), the unification algorithm
itself, and the occurs check that guards every variable binding.

Crucially, unification itself decides only **equality**, not sub-typing: it
never silently widens `Nat` into `Int`. The sub-sort ordering is handled one
level up, by the solver, which asks the `Unifier` for the strict
super-sorts and sub-sorts of a node instead of relying on unification to
widen anything — and only ever for the **materializable** relation from the
lattice section above, not the full sub-sort ordering, so container-element
covariance and function variance never show up as candidates even though
they hold in the lattice. This separation keeps unification simple and
total, and confines every coercion decision to the ranked search below,
where it can be measured and compared; see [the subsort
lattice](inference/unification.md#the-subsort-lattice) for exactly what the
solver enumerates and in which order.

## Ranked backtracking search

The solver walks the constraints in generation order, and at each choice
point it tries the alternatives and recurses. Because inference must pick not
just *a* typing but the *best* one, every leaf of the search is scored by a
lexicographic **measure**, and the solver keeps the single best leaf:

- each [`Sub`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Sub), [`Lit`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Lit) and [`Join`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Join) source contributes one measure component — `0`
  for an exact match, and a larger number for a wider coercion (the number of
  steps up the sub-sort chain);
- components are ordered by generation position, earlier ones most
  significant, so a coercion high in the expression tree costs more than one
  deep inside it;
- [`Disjunction`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Disjunction) and [`Comprehension`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Comprehension) contribute *no* component of their own
  but are explored exhaustively.

The minimum measure is the most specific typing: equality beats widening,
nearer widenings beat farther ones, and literals take their smallest
admissible sort. Each choice point does the same thing — **try equality
first, then the strict widenings in ascending distance** — so the first
solution found down any branch is already the locally cheapest. Backtracking
itself reuses the `Unifier`'s snapshot/rollback — see [Snapshot and
rollback](inference/unification.md#snapshot-and-rollback) — and [The
solver](inference/solver.md#the-solver) walks through the full pseudocode of
how each constraint kind is discharged.

Two properties make the search both correct and tractable, and both are
*exact*, not heuristic, because earlier measure components dominate the
lexicographic order — see
[`Dominated`](inference/solver.md#branch-and-bound-dominated) for the
pruning check itself:

- **Exhaustive disjunctions detect ambiguity.** Because every overload and
  every comprehension reading is explored, two distinct solutions that tie at
  the same minimum measure are reported as a genuine *ambiguity* error rather
  than silently picking one.
- **Branch-and-bound pruning keeps it fast.** A partial branch whose measure
  prefix is already strictly worse than the best leaf found so far is cut
  immediately rather than explored to a full leaf, so an equation with many
  independent overloaded operators need not explore every combination to its
  leaf.

When the best leaf still leaves a sort variable free — an auxiliary sort that
no constraint ever pinned down, such as the element sort of an empty
container that is never used — the solver substitutes a default so the
equation is accepted rather than reported as underdetermined; see [Scoring
and extracting](inference/solver.md#scoring-and-extracting-leaf-extract) for
how that default is computed.

The inferred sorts are recorded in side tables mapping each expression to its
resolved sort and each name occurrence to the chosen overload, keyed by the
same [`ExprId`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/type.ExprId.html) numbering the generator used, ready for
[lowering](../rewriting/lowering.md) to re-walk.

Because this global ranked search considers the whole equation at once, it
accepts some specifications that a purely local algorithm rejects as
ambiguous — for example resolving an overloaded call by ranking an exact
match strictly above one that needs a numeric up-cast, or typing a `where`
clause by solving all of its bindings jointly instead of one at a time.

## A worked example

The same measure-driven ranking governs overload disjunctions, literals and
container joins alike. [Inference Internals works through a two-overload
disjunction end to
end](inference/solver.md#worked-example-an-eagerly-bound-argument-pruning-a-disjunct),
with the full pseudocode of how each candidate is tried and scored; the two
examples below show what that same ranking looks like for the other
constraint kinds.

In `map g: Real; eqn g = 1;`, the literal `1` is tried most-specific-first: `Pos` (generality `0`)
before `Nat`, `Int`, `Real`. `Pos` is consistent — it widens to `Real` at the
equation's join — so the leaf that types the literal itself as `Pos` and pays
the widening at the coercion point has a smaller measure than one that starts
the literal at `Real`. The literal is therefore typed `Pos` and coerced,
matching the rule that literals take their smallest admissible sort.

For a container example, `s == t` with `s: FSet(Pos)` and `t: Set(Pos)`
shares one variable `?a` between the operands. The [`Join`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Join) computes the least
upper bound $FSet(Pos) \sqcup Set(Pos) = Set(Pos)$, charging one widening step
to the `FSet(Pos)` source and `0` to the already-`Set(Pos)` source — so both
operands agree on the least sort that admits them, `Set(Pos)`, and the
comparison is typed there.
