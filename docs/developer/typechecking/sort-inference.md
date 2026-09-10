```math_preamble

\usepackage{tikz}
```
# Sort Inference

Phase 3 of the pipeline is the heart of the crate: given a fully desugared
equation and a [signature](signature.md) to resolve names against, it decides
the sort of every sub-expression, choosing between overloaded operators and
inserting the implicit coercions the surface language leaves out. It runs **per
equation**, as a memoized query, in two steps — constraint generation, then a
ranked backtracking search — both described in detail below.

## The sort lattice

Sort inference works over an interned lattice of *resolved* sorts, which is
the vocabulary shared by unification and the solver. A `ResolvedSort` is one
of:

- a primitive sort (`Bool`, `Pos`, `Nat`, `Int`, `Real`);
- a container sort `op(S)` such as `List(S)`, `Set(S)` or `FBag(S)`;
- a function sort $A_0 \# \dots \# A_n \to B$;
- a nominal sort `Def(d)`, identified by the declaration `d` it resolves to;
- a `Unit` sort, used internally for the result of an action;
- a bound type variable `Var(id)`, scoped to whichever polymorphic template
  declared it. It is a genuine lattice element on the same footing as the
  others — not a syntax-tree placeholder — but it never survives past sort
  inference: [instantiating a scheme](system-specification.md#the-polymorphic-signature)
  replaces every occurrence of one `Var` with a fresh unification variable
  before the constraint generator emits anything downstream of it, so
  lowering and the LSP-facing `sort_expression` both treat reaching a `Var`
  as an invariant violation (`unreachable!`) rather than a case to handle.
  Two `Var`s compare equal only when their ids match, and — like `Def` — a
  `Var` never joins or meets with anything, itself included at a different
  id: a bound variable is opaque to the coercion lattice, exactly as it must
  be for `in: S # List(S) -> Bool` to mean "the same `S`" on both sides
  without secretly widening.

Because sorts are **interned**, each distinct sort is stored once and two
sorts are equal exactly when their indices are equal — a sort comparison is a
single integer comparison. Sub-sorts are stored as indices too, so a
`ResolvedSort` is small and structural equality never has to recurse.

Unlike the plain set of sorts in the book, these sorts form a **lattice**
under the sub-sort ordering that the implicit coercions define:

- the number sorts form a chain $Pos \leq Nat \leq Int \leq Real$;
- the finite containers embed into their unbounded counterparts,
  $FSet(S) \leq Set(S)$ and $FBag(S) \leq Bag(S)$, when the element sorts are
  equal;
- all other distinct sorts are incomparable.

The lattice supplies a **join** (least common supersort) and **meet**
(greatest common subsort). A join is what lets two branches of an `if`, or the
two sides of an equation, meet at a single common sort: joining `Nat` and
`Int` yields `Int`, and joining `FSet(Pos)` and `Set(Pos)` yields `Set(Pos)`.
This directly models the numeric up-casting and container widening that the
surface language performs silently, but as a clean lattice operation rather
than a collection of special cases.

## Constraint generation

The generator walks the lowered condition, left-hand side and right-hand side
of one equation and, for every sub-expression, allocates a *sort node* in the
unifier (see below) and emits constraints relating those nodes. Nodes are
numbered by an `ExprId` in a fixed order — parents before children, and within
an application the **arguments before the applied function**. This ordering
matters: by the time the solver reaches a function's overload choice, the
argument sorts are already known, so most overloads can be rejected
immediately.

The constraint kinds are:

- **Sub** — the sort of one node must be a sub-sort of another, modelling an
  implicit up-cast (a `Nat` argument passed where `Int` is expected). Equality
  is the special case where no coercion is needed.
- **Lit** — a number literal must take a number sort admitting its kind (`0`
  is a natural, every other literal is positive). Literals prefer the most
  specific sort, so `1` is a `Pos` before it is widened.
- **Disjunction** — a name with several overloads must resolve to exactly one
  of them. The solver commits to one disjunct per solution.
- **Comprehension** — a set/bag comprehension `{ x: S | e }` reads as a
  `Set(S)` when its body is boolean and as a `Bag(S)` when its body is a
  number; the reading follows from the solved body sort.
- **Numeric** — an application of an arithmetic operator (`+`, `-`, `*`, `/`,
  `div`, `mod`, `exp`, `max`, `min`) with no user overload. Because the
  built-in overloads of these operators never overlap on their argument
  sorts, at most one can match a fully-known argument tuple, so this is
  resolved by a direct lookup rather than by branching. Treating them this
  way — instead of as a general disjunction — is what keeps equations with
  many repeated arithmetic sub-expressions from blowing up combinatorially.
- **Join** — a group of `Sub` constraints that all widen into the *same*
  shared sort variable (the operands of a comparison, the branches of an
  `if`, a set or bag element, the equation's two sides) is folded into one
  least-upper-bound over the lattice. Computing the common supersort in a
  single step avoids the order-sensitivity of solving the sub-constraints one
  at a time, where an early finite-container branch could otherwise fix the
  result prematurely and force the other branch to be re-explored.

Structural facts that must hold in *every* solution — that a callee has a
function sort, that a condition is boolean — are unified eagerly at
generation time, so a violation is reported as a direct error rather than a
silent search failure.

Equations whose binders use a sort that inference does not model yet (an
anonymous `struct`, a bare product) are left untyped rather than rejected, so
the rest of the specification still type checks.

## Unification with subtyping

Equality of sorts is decided by structural **unification** over a union-find
table. merc uses [`ena`](https://crates.io/crates/ena) — the Rust compiler's
extracted unification-table crate — for the union-find, wrapped in a
`Unifier` that adds an arena of sort nodes and the sub-sort operations.

A sort node under inference is one of: a fully resolved (interned) sort, a
container `op(subsort)` whose element may still contain variables, a function
sort whose parts may contain variables, or a bare **unification variable**. A
node like `List(?t)` — a list whose element sort `?t` is still unknown — is
how the generator represents an empty-list literal before the element sort is
pinned down.

Unification proceeds by the usual structural rules, with two additions
specific to this checker:

- **Interning makes the base case trivial.** Two fully resolved sorts unify
  exactly when their indices are equal, so unification only ever spells out
  structure around the variables that remain.
- **A resolved container or function sort unifies against a spelled-out
  one** by matching head constructors and recursing into the sub-sorts. This
  lets a half-known `List(?t)` unify with a fully resolved `List(Nat)` by
  binding `?t := Nat`.

Binding a variable runs an **occurs check** first, which rejects the infinite
sort a binding like `?t := List(?t)` would otherwise create.

Crucially, unification itself decides only **equality**, not sub-typing. The
sub-sort ordering is handled one level up, by the solver: unification never
silently widens `Nat` into `Int`. Instead, the `Unifier` exposes the strict
super-sorts and sub-sorts of a node — `Pos` yields `[Nat, Int, Real]`, `Real`
yields `[Int, Nat, Pos]` — in ascending distance, and only the head
constructor is widened (`Nat` has supersorts; `List(Nat)` does not). The
solver enumerates these candidates explicitly when a plain equality does not
hold. This separation keeps unification simple and total, and confines every
coercion decision to the ranked search where it can be measured and compared.

## Ranked backtracking search

The solver walks the constraints in generation order, and at each choice
point it tries the alternatives and recurses. Because inference must pick not
just *a* typing but the *best* one, every leaf of the search is scored by a
lexicographic **measure**, and the solver keeps the single best leaf:

- each `Sub`, `Lit` and `Join` source contributes one measure component — `0`
  for an exact match, and a larger number for a wider coercion (the number of
  steps up the sub-sort chain);
- components are ordered by generation position, earlier ones most
  significant, so a coercion high in the expression tree costs more than one
  deep inside it;
- `Disjunction` and `Comprehension` contribute *no* component of their own
  but are explored exhaustively.

The minimum measure is the most specific typing: equality beats widening,
nearer widenings beat farther ones, and literals take their smallest
admissible sort. Each choice point does the same thing — **try equality
first, then the strict widenings in ascending distance** — so the first
solution found down any branch is already the locally cheapest.

Backtracking is implemented with the union-find table's native
**snapshot / rollback**. Before trying an alternative the solver snapshots
the variable bindings; if the branch dead-ends or is exhausted, it rolls back
to free exactly the variables bound since the snapshot. The sort-node arena
is append-only and is *not* rolled back — nodes created inside an abandoned
branch simply remain as harmless garbage — which keeps rollback to the cheap
union-find operation.

Two properties make the search both correct and tractable:

- **Exhaustive disjunctions detect ambiguity.** Because every overload and
  every comprehension reading is explored, two distinct solutions that tie at
  the same minimum measure are reported as a genuine *ambiguity* error rather
  than silently picking one.
- **Branch-and-bound pruning keeps it fast.** A partial branch whose measure
  prefix is already strictly worse, component for component, than the best
  leaf found so far can never win — earlier components dominate the
  lexicographic order — so it is cut immediately. Without this, an equation
  with many independent overloaded operators would explore every combination
  to its leaf; with it, the search stays practical. The pruning is *exact*:
  it changes only how much of the tree is visited, never which typing wins or
  which equations are ambiguous.

When the best leaf still leaves a sort variable free — an auxiliary sort that
no constraint ever pinned down, such as the element sort of an empty
container that is never used — the solver substitutes a default so the
equation is accepted rather than reported as underdetermined.

The inferred sorts are recorded in side tables mapping each expression to its
resolved sort and each name occurrence to the chosen overload, keyed by the
same `ExprId` numbering the generator used, ready for [lowering](lowering.md)
to re-walk.

Because this global ranked search considers the whole equation at once, it
accepts some specifications that a purely local algorithm rejects as
ambiguous — for example resolving an overloaded call by ranking an exact
match strictly above one that needs a numeric up-cast, or typing a `where`
clause by solving all of its bindings jointly instead of one at a time.

## A worked example

Consider two overloads of the same name and a call that fits both:

```mcrl2
map  f: Nat -> Nat;
     f: Int -> Int;
var  n: Nat;
eqn  f(n) = n;
```

Generation numbers the argument `n` before the callee `f`, so by the time
`f`'s overload `Disjunction` is reached the argument sort is already known to
be `Nat`. Two disjuncts then unify:

- `f: Nat -> Nat` — the argument `Nat` matches the parameter `Nat` exactly, so
  the argument's `Sub` contributes measure component `0`;
- `f: Int -> Int` — the argument `Nat` must widen to `Int`, one step up the
  number chain, so the same `Sub` contributes `1`.

Both branches reach a leaf: the call type-checks either way. The measures
differ only in that argument component — `[…, 0, …]` versus `[…, 1, …]` — and
because `0 < 1` the exact `Nat -> Nat` overload wins. A plain "disjunction
handed to unification" would have no reason to prefer it; the measure is
exactly what rules out the needless up-cast.

The same ranking governs literals. In `f(n) = n`'s sibling `map g: Real; eqn g
= 1;`, the literal `1` is tried most-specific-first: `Pos` (generality `0`)
before `Nat`, `Int`, `Real`. `Pos` is consistent — it widens to `Real` at the
equation's join — so the leaf that types the literal itself as `Pos` and pays
the widening at the coercion point has a smaller measure than one that starts
the literal at `Real`. The literal is therefore typed `Pos` and coerced,
matching the rule that literals take their smallest admissible sort.

For a container example, `s == t` with `s: FSet(Pos)` and `t: Set(Pos)`
shares one variable `?a` between the operands. The `Join` computes the least
upper bound $FSet(Pos) \sqcup Set(Pos) = Set(Pos)$, charging one widening step
to the `FSet(Pos)` source and `0` to the already-`Set(Pos)` source — so both
operands agree on the least sort that admits them, `Set(Pos)`, and the
comparison is typed there.
