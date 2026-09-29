```math_preamble

\usepackage{algpseudocode}
```
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

Unification decides whether two sort nodes *could* denote the same sort, and
if so commits to that by binding whatever variables stand in the way. The
underlying rule is the standard one for structural unification over a term
algebra with variables: a variable unifies with anything (binding itself to
it, after an occurs check), and two non-variable terms unify only if they
have the same head constructor, recursively unifying their corresponding
arguments. What is specific to this checker is *where* the variables can
hide — inside a union-find table rather than only at the leaves — which is
exactly what `shallow_normalize` accounts for below.

### Chasing variables: `shallow_normalize`

A sort node that is a `Var` is not necessarily still a hole: it may have been
bound to something else already, or merged into a union-find class that
another `Var` in the same equation was later bound through. Before `unify`
(or anything else) can inspect a node's shape, it has to follow that chain of
indirection to whatever it currently resolves to — the same "find" step any
union-find structure needs before comparing two elements.

```math
\begin{algorithmic}[1]
\Function{ShallowNormalize}{$id$}
  \While{$\mathit{arena}[id] = \Call{Var}{v}$ and $\mathit{table}$ binds $v$ to $\mathit{next}$}
    \State $id \gets \mathit{next}$ \Comment{follow the binding chain}
  \EndWhile
  \State \Return $id$ \Comment{either non-\textsc{Var}, or an unbound \textsc{Var}}
\EndFunction
\end{algorithmic}
```

It is called *shallow* because it only chases indirection at the node's own
level — it does not recurse into a node's children. `Generic{List, ?t}` is
returned as-is even if `?t` itself happens to already be bound to `Nat`
somewhere in the table; only [`resolve`](#resolving-a-solved-node), further
down this page, walks all the way to the leaves. This is exactly what makes
`shallow_normalize` cheap enough to call before every comparison unification
makes, rather than something that has to be reserved for a final pass.

**Example.** Suppose `?a` and `?b` were merged (a pure union-find union, no
value attached to either yet), and `?b` was later bound to `Nat`:

```
?a ---(same class as)---> ?b ---(bound to)---> Nat
```

`shallow_normalize(?a)` follows the class to `?b`, finds it bound, and
returns `Nat`'s node — in one step, regardless of how many variables were
chained together to get there. Called again on that same result, it is a
no-op: `Nat`'s node is not a `Var`, so the loop never starts.

### The algorithm

```math
\begin{algorithmic}[1]
\Function{Unify}{$lhs, rhs$}
  \State $lhs \gets \Call{ShallowNormalize}{lhs}$
  \State $rhs \gets \Call{ShallowNormalize}{rhs}$
  \If{$lhs = rhs$}
    \State \Return $\mathit{true}$ \Comment{same arena node — trivially equal}
  \EndIf
  \If{$lhs$ and $rhs$ are both unbound \textsc{Var}s}
    \State merge the two union-find classes \Comment{always succeeds}
    \State \Return $\mathit{true}$
  \ElsIf{$lhs$ is an unbound \textsc{Var} $v$}
    \State \Return $\Call{Bind}{v, \mathit{arena}[rhs]}$
  \ElsIf{$rhs$ is an unbound \textsc{Var} $v$}
    \State \Return $\Call{Bind}{v, \mathit{arena}[lhs]}$
  \ElsIf{$lhs = \Call{Resolved}{a}$ and $rhs = \Call{Resolved}{b}$}
    \State \Return $a = b$ \Comment{interning: one integer compare}
  \ElsIf{one side is $\Call{Resolved}{r}$ and the other is $\Call{Generic}{op, s}$}
    \State \Return $op$ matches $r$'s head constructor, and $\Call{Unify}{s, r\text{'s element sort}}$
  \ElsIf{one side is $\Call{Resolved}{r}$ and the other is $\Call{Function}{D, R}$}
    \State \Return arities agree, and $\Call{Unify}$ holds on every domain pair and on $(R, r\text{'s range})$
  \ElsIf{$lhs = \Call{Generic}{op_1, s_1}$ and $rhs = \Call{Generic}{op_2, s_2}$}
    \State \Return $op_1 = op_2$ and $\Call{Unify}{s_1, s_2}$
  \ElsIf{$lhs = \Call{Function}{D_1, R_1}$ and $rhs = \Call{Function}{D_2, R_2}$}
    \State \Return equal arity, and $\Call{Unify}$ holds on all domain pairs and on $(R_1, R_2)$
  \Else
    \State \Return $\mathit{false}$ \Comment{shape mismatch}
  \EndIf
\EndFunction
\end{algorithmic}
```

```math
\begin{algorithmic}[1]
\Function{Bind}{$v, \mathit{value}$}
  \If{$\Call{Occurs}{v, \mathit{value}}$}
    \State \Return $\mathit{false}$ \Comment{reject $?t \mathrel{:=} List(?t)$}
  \EndIf
  \State record $v \mapsto \mathit{value}$ in the union-find table
  \State \Return $\mathit{true}$
\EndFunction
\end{algorithmic}
```

`Unify` is symmetric in `lhs`/`rhs`: every arm above is written to match
either side being the `Var`, the `Resolved`, or the `Generic`/`Function`
(the actual code uses `|`-patterns for exactly this), so `Unify(a, b)` and
`Unify(b, a)` normalize, compare, and bind identically — argument order never
changes whether two sorts unify or what they end up bound to. That is by
design: `unify` only ever answers "are these equal," and equality has no
direction. The strict-subsort ordering further down this page is where
direction *does* matter, and for an unrelated reason — see
[the subsort lattice](#the-subsort-lattice) below.

**Example.** Typing an empty list literal `#[]` against an expected sort
`List(Pos)` compares the resolved leaf `List(Pos)` against the literal's
still-open `Generic{List, ?t}`:

```
Unify(Resolved(List(Pos)), Generic{List, ?t})
  both sides already non-Var, no normalization to do
  head constructors agree (List = List)
  -> Unify(Pos, ?t)
       rhs is an unbound Var  ->  Bind(?t, Pos)
       Occurs(?t, Pos) = false, so the bind succeeds
```

`?t` ends up bound to `Pos`, and the literal's sort resolves to `List(Pos)`.

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

`Bind` refuses a binding that would create an infinite sort — the standard
occurs check for a unifier with structural terms, walking the same shape
`Unify` itself recurses over:

```math
\begin{algorithmic}[1]
\Function{Occurs}{$v, id$}
  \State $id \gets \Call{ShallowNormalize}{id}$
  \If{$\mathit{arena}[id] = \Call{Var}{u}$}
    \State \Return $v$ and $u$ are in the same union-find class
  \ElsIf{$\mathit{arena}[id] = \Call{Resolved}{}$}
    \State \Return $\mathit{false}$
  \ElsIf{$\mathit{arena}[id] = \Call{Generic}{\_, s}$}
    \State \Return $\Call{Occurs}{v, s}$
  \ElsIf{$\mathit{arena}[id] = \Call{Function}{D, R}$}
    \State \Return $\bigl(\exists\, d \in D : \Call{Occurs}{v, d}\bigr) \lor \Call{Occurs}{v, R}$
  \EndIf
\EndFunction
\end{algorithmic}
```

The `shallow_normalize` call at the top matters here too: it is what lets the
check see through a variable that was bound (or merged) *after* the sort
expression containing it was built, rather than only through variables that
were already resolved when the recursion started.

**Example.** `?t` unified against `List(?t)`: `Bind` calls
`Occurs(?t, Generic{List, ?t})`, which normalizes (no-op, it is already a
`Generic`), recurses into the element sort, normalizes `?t` again (still an
unbound `Var`), and finds it in `?t`'s own union-find class — rejected.

The same rejection fires through an *indirect* cycle: merge `?a` and `?alias`
into one class first (`Unify(?a, ?alias)`, both still unbound), then attempt
`Unify(?a, Generic{List, ?alias})`. `Bind` calls `Occurs(?a, Generic{List,
?alias})`, which recurses to `?alias`, and `table.unioned` reports that `?a`
and `?alias` share a class — even though nothing points from `?alias` back to
`?a` by pointer identity. That is precisely why the check compares union-find
*classes* rather than node identity: a cycle introduced indirectly, through a
prior merge, is just as infinite a sort as a direct self-reference.

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

Only the **head constructor** widens through this enumeration: `Nat` yields
several entries, `List(Nat)` yields none. That is not because `List(Nat)` has
no supersorts at all — container-element covariance makes `List(Nat) <:
List(Int)` a genuine relation in the full sub-sort lattice (see [the sort
lattice](../sort-inference.md#the-sort-lattice)) — but this function only
ever widens the numeric chain and the finite/infinite container pairing, and
neither reaches inside a container's element; the covariant step exists but
isn't one of the coercions lowering can materialize (again, see the lattice
page), so it is never offered as a candidate here. This is exactly
`number_generality`'s table
(`Pos = 0, Nat = 1, Int = 2, Real = 3`) read in each direction, plus the two
hard-coded container pairs (`FSet <: Set`, `FBag <: Bag`).

Unlike `unify`, this ordering is **not** symmetric — `strict_super_sorts` and
`strict_sub_sorts` answer different questions (what sits above `id`, versus
what sits below it), matching `<:` itself being directional (`Pos <: Nat`
holds, `Nat <: Pos` doesn't). A [`Sub`](solver.md#the-solver) constraint's
`lhs` and `rhs` inherit that same directionality and are not interchangeable
for it: `Sub { lhs, rhs }` means "`lhs` must be a subsort of `rhs`," so
swapping them asks a different question, not the same one twice.
[`solve_widening`](solver.md#subsorting-solve_sub-solve_widening) is built
around exactly this asymmetry — it enumerates `strict_super_sorts(lhs)`
first (widening `lhs` upward toward `rhs`), falling back to
`strict_sub_sorts(rhs)` (narrowing `rhs` downward toward `lhs`) only when
`lhs`'s own shape isn't concrete enough to enumerate from. None of this
reaches into `unify` itself, which stays a pure, order-independent equality
check throughout — the directionality lives entirely in the solver's choice
of *which* pair to try unifying next, never in what `unify` does with the
pair it's given.

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

See [the `#[]` against `List(Pos)` example](#the-algorithm) above for a
structural bind, and [the occurs-check examples](#the-occurs-check) for how
a direct and an indirect cycle are both rejected. One more is worth spelling
out on its own, since it does not go through `Bind` at all:

**Transitive merging.** `?a` and `?b` are unified while both are still
unbound (a pure merge, no structure touched); `?b` is bound to `Bool`
afterwards. `resolve(?a)` follows the merged class to `?b`'s binding and
returns `Some(Bool)` — this is the mechanism behind a scheme like
`==: S # S -> Bool`, where both operands share one type variable `S` before
either side's own sort is known.
