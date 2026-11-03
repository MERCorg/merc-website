```math_preamble

\usepackage{algpseudocode}
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
```
# The Unifier

The unifier of [sort inference](../sort-inference.md) solves sort equality by structural unification over a union-find table, backed by
[`ena`](https://crates.io/crates/ena) — the same crate the Rust compiler's own
type inference uses. It is a single-purpose component: given two sort
expressions that may still contain holes, decide whether they can be made
equal, and if so, make them so. It has no notion of equations, overloads,
subtyping or ranking — that all lives one level up, in [the ranked
backtracking search](ranked-backtracking.md) and in [sort
inference](../sort-inference.md).

Apart from the concrete term shapes below, nothing here is specific to sorts:
it is standard first-order unification over a term algebra whose leaves may
be holes, extended with snapshot and rollback so a backtracking search can
try a binding and undo it.

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

- an `InferSortId` is just "a node in the arena" — **structural**, not
  deduplicated. Two different ids can denote the same sort (e.g. two
  occurrences of `List(?t)` built independently), and only `unify` decides
  whether they are semantically equal.
- a `SortVar` is a union-find key. It is what a `Var` node wraps, and it is the
  only thing `snapshot`/`rollback_to` checkpoint.

`resolved_node` memoizes `Resolved(id) -> InferSortId` in a side table, so
repeated references to the same already-known sort (e.g. re-fetching `Nat`
for every argument of `+`) share one arena node rather than allocating a
fresh one each time.

<a id="def-sorts-with-holes"></a>**Definition 1 (sorts with holes).** A *sort with holes* is a term built from
resolved sorts ([Sort inference, Definition 1](../sort-inference.md#def-sorts-and-subsorts)), container heads $op(\cdot)$ and function sorts
$\cdot \# \dots \# \cdot \to \cdot$, whose leaves may be *holes*: sort
variables still to be determined. An *assignment* maps holes to sorts with holes;
it *unifies* two sorts with holes if applying it to both gives the same term.

A resolved sort counts as the ground term it denotes, so `List(?t)` and the
resolved `List(Nat)` are unified by $?t := \mathit{Nat}$. A rigid type variable
([Type variables and polymorphic schemes, Definition 1](../polymorphism.md#def-scheme), [Type variables and polymorphic schemes, Theorem 1](../polymorphism.md#thm-checking-a-template-once)) is a constant, not a hole.

## Unification

Unification decides whether two sort nodes *could* denote the same sort, and
if so commits to that by binding whatever holes stand in the way. The
underlying rule is the standard one for structural unification over a term
algebra with variables (here, holes): a variable unifies with anything (binding itself to
it, after an occurs check), and two non-variable terms unify only if they
have the same head constructor, recursively unifying their corresponding
arguments. What is specific to this checker is *where* the holes can
hide — inside a union-find table rather than only at the leaves — which is
exactly what `shallow_normalize` accounts for below.

### Chasing variables: `shallow_normalize`

A sort node that is a `Var` is not necessarily still a hole: it may have been
bound to something else already, or merged into a union-find class that
another `Var` in the same equation was later bound through. Before `unify`
(or anything else) can inspect a node's shape, it has to follow that chain of
indirection to whatever it currently resolves to — the same "find" step any
union-find structure needs before comparing two elements.

```math algorithm
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

### The algorithm {#the-algorithm}

```math algorithm
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

```math algorithm
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
direction. The sub-sort ordering is where direction *does* matter, and it is
deliberately kept out of the unifier — see [Ordering is not
unification](#ordering-is-not-unification) below.

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

- **Interning collapses the base case.** Two `Resolved` leaves unify by
  comparing their interned ids — no recursion needed even for a deeply
  nested sort, as long as neither side still has a hole in it.
- **A resolved sort unifies directly against a spelled-out one.** A
  half-known `Generic{List, ?t}` (an empty list literal) unifies against the
  fully resolved `List(Nat)` by looking up `List(Nat)`'s element sort in the
  interner and unifying `?t` against it — the resolved side never needs to be
  "expanded" into its own arena nodes up front.

The union-find table only ever merges two classes while both are still
unbound: two bound classes are unified structurally, by recursing into their
values, and never merged wholesale. That is what makes transitive merging safe:
`?a = ?b` merges two holes, a later `?b := Bool` binds the merged class, and
resolving `?a` afterwards finds `Bool`.

<a id="thm-unification"></a>**Theorem 1 (unification).** `Unify(a, b)` succeeds if and only if some
assignment unifies $a$ and $b$, and on success the bindings it adds are a most
general such assignment. `Unify` is symmetric in its arguments, and the occurs
check guarantees that every bound hole resolves to a finite term.

*Proof idea.* This is standard first-order unification with an occurs check
(Robinson, 1965), over the term algebra of Definition 1; union-find only changes
how the assignment is represented. It is not formalised in Lean.

### The occurs check {#the-occurs-check}

`Bind` refuses a binding that would create an infinite sort — the standard
occurs check for a unifier with structural terms, walking the same shape
`Unify` itself recurses over:

```math algorithm
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

## Resolving a solved node {#resolving-a-solved-node}

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
underdetermined. What `default` is, is decided by the caller, not the
`Unifier`; for sort inference see [Underdetermined
defaults](../sort-inference.md#underdetermined-defaults).

## Ordering is not unification {#ordering-is-not-unification}

Unification only ever decides **equality**; it never widens `Nat` into `Int`.
A sub-sort ordering is layered on top by the client: the `Unifier` offers
`strict_super_sorts`/`strict_sub_sorts` to enumerate the neighbours of a node,
and the solver tries unifying against each of them in turn. Which neighbours
exist, and in what order, is a property of the sort lattice, described in
[Widening over the lattice](../sort-inference.md#coercions).
This keeps `unify` simple, total and order-independent, and confines every
coercion decision to the search, where it can be scored.

## Snapshot and rollback

```
snapshot():  return table.snapshot()          -- ONLY the union-find bindings
rollback_to(s): table.rollback_to(s.snapshot) -- undoes bindings made since `s`
```

This is the entire backtracking contract the solver relies on for every
resolution it tries and discards.
Crucially, it checkpoints **only** `table` — the union-find bindings. The
`arena` is append-only and is never part of a snapshot: any node pushed by
`generic`, `function`, `resolved_node`, or `fresh_var` while a branch that
later gets rolled back was being explored simply stays in the `Vec` forever,
unreachable but not freed.

This is deliberate, and it is harmless because of *scope*, not
because the arena is somehow reclaimed: inference constructs a fresh
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
