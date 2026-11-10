```math_preamble

\usepackage{algpseudocode}
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
```
# Sort inference

Sort inference decides the sort of every sub-expression of an equation, chooses
between overloaded operators, and inserts the implicit coercions that the surface
language leaves out. It assumes the signature ([Signature and well-typedness, Definition 1](signature.md#def-signature)) to
resolve names against, and runs once per equation, in two steps: it *generates*
constraints, and then a [ranked backtracking search](inference/ranked-backtracking.md)
*solves* them, using [the unifier](inference/unification.md) to decide sort
equality. Those two pages describe the general machinery; this page defines what
is specific to sorts: the subsort order, coercions, the constraints, and how a
typing is ranked (Definitions 1 to 4).

## The subsort order {#the-subsort-order}

<a id="def-sorts-and-subsorts"></a>**Definition 1 (sorts and subsorts).** A *resolved sort* is one of

- a basic sort `Bool`, `Pos`, `Nat`, `Int` or `Real`;
- a container sort $op(S)$, for $op$ one of `List`, `Set`, `Bag`, `FSet`,
  `FBag`;
- a function sort $A_1 \# \dots \# A_n \to B$;
- a nominal sort, identified by the declaration it resolves to;
- a type variable ([Type variables and polymorphic schemes, Definition 1](polymorphism.md#def-scheme));
- the unit sort, used internally as the sort of an action.

The *subsort order* $\leq$ is the least partial order, following Definition
15.1.8 of the book, such that

- $\mathit{Pos} \leq \mathit{Nat} \leq \mathit{Int} \leq \mathit{Real}$;
- $\mathit{FSet}(S) \leq \mathit{Set}(S)$ and $\mathit{FBag}(S) \leq \mathit{Bag}(S)$;
- containers are covariant: $op(S) \leq op(T)$ if $S \leq T$;
- function sorts are contravariant in their domain and covariant in their range:
  $(A_1 \# \dots \# A_n \to B) \leq (A'_1 \# \dots \# A'_n \to B')$ if
  $A'_i \leq A_i$ for all $i$ and $B \leq B'$.

All other distinct sorts are incomparable. The order has a partial *join*
$\sqcup$ (least common supersort) and *meet* $\sqcap$ (greatest common subsort):
$\mathit{Nat} \sqcup \mathit{Int} = \mathit{Int}$ and
$\mathit{FSet}(\mathit{Pos}) \sqcup \mathit{Set}(\mathit{Pos}) = \mathit{Set}(\mathit{Pos})$.
The join is what lets the two branches of an `if`, or the two sides of an
equation, meet at one sort.

Resolved sorts are interned: each distinct sort is stored once, and two sorts are
equal exactly when their indices are, so comparing two sorts is one integer
comparison.

## Coercions {#coercions}

Not every step $S \leq T$ has a coercion that builds a term of sort $T$ from a
term of sort $S$.

<a id="def-coercible"></a>**Definition 2 (coercible).** $S$ is *coercible* to $T$, written
$S \sqsubseteq T$, if $S = T$ or

- $S$ and $T$ are number sorts with $S \leq T$;
- $S = \mathit{FSet}(U)$ and $T = \mathit{Set}(U)$, or $S = \mathit{FBag}(U)$ and
  $T = \mathit{Bag}(U)$, with the same element sort $U$;
- $S = (D \to R)$ and $T = (D \to R')$, with the same domain $D$ and
  $R \sqsubseteq R'$. The coercion is the eta-expansion
  $\lambda d{:}D.\ \mathit{coerce}(f(d))$.

The *strict supersorts* of $S$ are the sorts $T \neq S$ with
$S \sqsubseteq T$ that change only the head of $S$: for a number sort the wider
number sorts, nearest first (`Pos` gives `Nat`, `Int`, `Real`); for `FSet` and
`FBag` the unbounded container; for a function sort the function sorts with the
same domain and a strict supersort of the range. The *strict subsorts* are
defined in the opposite direction.

Coercions are exactly the conversions that the surface language inserts
silently. Element-wise container covariance, $\mathit{List}(\mathit{Pos}) \leq
\mathit{List}(\mathit{Nat})$, and contravariance in a function domain are in the
subsort order, but not coercible: there is no element-wise traversal that builds
the wider term. The search only tries coercible steps, so an equation that needs
one of the other steps is rejected rather than accepted with a coercion that does
not exist.

[Unification](inference/unification.md) decides only equality, and never widens a
sort. The direction of $\sqsubseteq$ matters: a constraint "$S$ is coercible to
$T$" is solved by widening $S$ upwards through its strict supersorts, and only if
$S$ is still a hole, by narrowing $T$ downwards through its strict subsorts.

## Constraints

<a id="def-constraints"></a>**Definition 3 (constraints).** Every expression node of the equation gets a
*hole*, a sort still to be determined ([The Unifier, Definition 1](inference/unification.md#def-sorts-with-holes)). A constraint is one of

| constraint | meaning |
|---|---|
| $\mathit{Sub}(s, t)$ | $s \sqsubseteq t$; an implicit coercion, where equality needs none |
| $\mathit{Lit}(s, k)$ | the number literal of kind $k$ has sort $s$: `0` is natural, every other literal positive |
| $\mathit{Disjunction}(e, s, \{(f_1, s_1), \ldots\})$ | the name at $e$ resolves to exactly one of its overloads $f_i$, of sort $s_i$ |
| $\mathit{Comprehension}(b, s, S)$ | `{x: S \| b}` has sort `Set(S)` for a Boolean body $b$, and `Bag(S)` for a numeric one |
| $\mathit{Join}(\{s_1, \ldots, s_n\}, t)$ | $s_i \sqsubseteq t$ for every $i$, solved together |

Constraint generation walks the equation once. Nodes are numbered in a fixed
pre-order, parents before children, and within an application the **arguments
before the applied function**. The number is not stored on the node: every later
pass recomputes it by walking in the same order. Constraints are solved in this
order, so when an overloaded function is reached, its arguments usually already
have a known sort, and most overloads fail on their first unification.

Facts that must hold in every solution, such as that an applied expression has a
function sort, or that a condition is Boolean, are unified immediately during
generation, so that a violation is reported as a direct error rather than as a
failed search. A binder with a bare product sort is rejected immediately as well.

### Resolving names {#resolving-names}

A variable occurrence is already tied to its binder ([Sort and name resolution, Definition 1](name-resolution.md#def-variable-resolution)), and its sort
is the sort of that binder. Every other name is looked up in the signature:
every ground overload becomes a candidate with its own sort, and every scheme
becomes a candidate with a fresh instance ([Type variables and polymorphic schemes, Definition 2](polymorphism.md#def-instance)). No candidate is an
undeclared name; exactly one is used directly; several give a $\mathit{Disjunction}$.

Arithmetic operators have no constraint kind of their own: `+`, `-`, `*`, `div`,
`mod` and the others are ordinary overloaded mappings of the basic-sort
templates, resolved like a user's overloaded mapping.

### Shared targets become joins

Several $\mathit{Sub}$ constraints can have the same target: the two operands of
`==`, the branches of an `if`, the elements of a set, the two sides of an
equation. Solving them one after another is order-sensitive: the first one binds
the shared target by equality, and if that fixes, say, `FSet` from a set literal
before a source that only admits `Set` is solved, the later constraint fails and
the search backtracks needlessly. Therefore, after generation, all $\mathit{Sub}$
constraints whose targets are the same hole are replaced by one
$\mathit{Join}$, at the position of the last of them. The parameters of the
candidates of a $\mathit{Disjunction}$ are distinct holes, so they are never
merged this way.

## Ranking typings {#ranking-typings}

Each kind of constraint is discharged by trying its *resolutions*, in one of the
two ways of [ranked backtracking](inference/ranked-backtracking.md#trying-resolutions),
and each successful resolution may add a cost component to the measure of the
typing.

<a id="def-measure-of-a-typing"></a>**Definition 4 (measure of a typing).** The *measure* of a typing is the
sequence of cost components of its constraints, in solving order, where

| constraint | resolutions | discipline | cost |
|---|---|---|---|
| $\mathit{Disjunction}$ | each overload | exhaustive | none |
| $\mathit{Comprehension}$ | the `Set` or `Bag` reading | exhaustive | none |
| $\mathit{Sub}$ | equality, then each strict supersort, nearest first | first success | $0$ for equality, $1 + k$ for the $k$-th supersort |
| $\mathit{Lit}$ | each admissible number sort, most specific first | first success | the position of the sort in $\mathit{Pos}, \mathit{Nat}, \mathit{Int}, \mathit{Real}$ |
| $\mathit{Join}$ | the join $\sqcup$, then each source separately | first success | one component per source, as for $\mathit{Sub}$ |

The inferred typing is the one with the lexicographically least measure; two
typings with the least measure are an ambiguity ([Ranked Backtracking, Theorem 3](inference/ranked-backtracking.md#thm-outcome-of-the-search)).

So equality beats a coercion, a near coercion beats a far one, a literal takes
its most specific admissible sort, and a coercion early in the solving order,
high up in the expression, counts more than one deep inside it. Overload and
comprehension choices add no cost, so if two of them reach the least measure,
the equation is ambiguous.

### Overloads and comprehensions

```math algorithm
\begin{algorithmic}[1]
\Function{Discharge}{Disjunction($d$), $i$}
  \State $\mathit{found} \gets \textsc{false}$
  \For{$(\mathit{target}, \mathit{sort}) \in d.\mathit{disjuncts}$}
    \State $s \gets \Call{Snapshot}{}$
    \If{\Call{Unify}{$d.\mathit{sort}, \mathit{sort}$}}
      \State $\mathit{choices}.\Call{Push}{(d.\mathit{expr}, \mathit{target})}$
      \State $\mathit{found} \gets \Call{Solve}{i+1} \lor \mathit{found}$ \Comment{no early return}
      \State $\mathit{choices}.\Call{Pop}{}$
    \EndIf
    \State \Call{RollbackTo}{$s$}
  \EndFor
  \State \Return $\mathit{found}$
\EndFunction
\end{algorithmic}
```

A comprehension is discharged the same way over its three readings,
$(\mathit{Bool}, \mathit{Set})$, $(\mathit{Nat}, \mathit{Bag})$ and
$(\mathit{Pos}, \mathit{Bag})$ for the body and the comprehension, without
recording a choice.

### Coercions {#coercions}

```math algorithm
\begin{algorithmic}[1]
\Function{Widen}{$\mathit{lhs}, \mathit{rhs}, i$}
  \State $s \gets \Call{Snapshot}{}$
  \State $\mathit{found} \gets \textsc{false}$
  \If{\Call{Unify}{$\mathit{lhs}, \mathit{rhs}$}} \Comment{try equality first}
    \State push $0$ onto \textit{measure}
    \State $\mathit{found} \gets \Call{Solve}{i+1}$
    \State pop \textit{measure}
  \EndIf
  \State \Call{RollbackTo}{$s$}
  \If{$\mathit{found}$}
    \State \Return \textsc{true}
  \EndIf
  \State $\mathit{pairs} \gets \Call{StrictSuperSorts}{\mathit{lhs}} \times \{\mathit{rhs}\}$, \textbf{or else} $\{\mathit{lhs}\} \times \Call{StrictSubSorts}{\mathit{rhs}}$
  \If{neither side has an enumerable shape}
    \State \Return \textsc{false}
  \EndIf
  \For{$(\mathit{distance}, (\mathit{lhs}', \mathit{rhs}')) \in \mathit{pairs}$} \Comment{nearest first}
    \State $s \gets \Call{Snapshot}{}$
    \If{\Call{Unify}{$\mathit{lhs}', \mathit{rhs}'$}}
      \State push $1 + \mathit{distance}$ onto \textit{measure}
      \State $\mathit{found} \gets \Call{Solve}{i+1}$
      \State pop \textit{measure}
    \EndIf
    \State \Call{RollbackTo}{$s$}
    \If{$\mathit{found}$}
      \State \Return \textsc{true}
    \EndIf
  \EndFor
  \State \Return \textsc{false}
\EndFunction
\end{algorithmic}
```

`Widen` discharges a $\mathit{Sub}$ constraint, and is the fallback of a
$\mathit{Join}$. Trying the strict supersorts in ascending distance is enough for
the smallest coercion to win; the distances are never compared otherwise.

### Literals

A literal whose sort is already known has a single resolution: its sort must
admit the literal (`Pos` does not admit `0`), and it adds that sort's position
as its cost. Otherwise the literal is discharged like `Widen`, over the fixed
list $\mathit{Pos}, \mathit{Nat}, \mathit{Int}, \mathit{Real}$ for a positive
literal and $\mathit{Nat}, \mathit{Int}, \mathit{Real}$ for a natural one.

### Joins

```math algorithm
\begin{algorithmic}[1]
\Function{Discharge}{Join($j$), $i$}
  \State $\mathit{resolved} \gets [\Call{Resolve}{s} : s \in j.\mathit{sources}]$
  \If{some source in $\mathit{resolved}$ is unresolved}
    \State \Return \Call{JoinSeq}{$j.\mathit{sources}, j.\mathit{target}, 0, i$} \Comment{fallback}
  \EndIf
  \State $\mathit{lub} \gets \mathit{resolved}[0]$
  \For{$\mathit{next} \in \mathit{resolved}[1 \,.\,.\,]$}
    \If{$\mathit{lub} \sqcup \mathit{next}$ is undefined}
      \State \Return \Call{JoinSeq}{$j.\mathit{sources}, j.\mathit{target}, 0, i$}
    \EndIf
    \State $\mathit{lub} \gets \mathit{lub} \sqcup \mathit{next}$
  \EndFor
  \If{some source in $\mathit{resolved}$ is not coercible to $\mathit{lub}$}
    \State \Return \Call{JoinSeq}{$j.\mathit{sources}, j.\mathit{target}, 0, i$}
  \EndIf
  \State $s \gets \Call{Snapshot}{}$
  \If{\Call{Unify}{$j.\mathit{target}, \mathit{lub}$}}
    \For{$\mathit{source} \in \mathit{resolved}$}
      \State push the distance from $\mathit{source}$ to $\mathit{lub}$ onto \textit{measure}
    \EndFor
    \State $\mathit{found} \gets \Call{Solve}{i+1}$
    \State pop all pushed components
    \If{$\mathit{found}$}
      \State \Return \textsc{true}
    \EndIf
  \EndIf
  \State \Call{RollbackTo}{$s$}
  \State \Return \Call{JoinSeq}{$j.\mathit{sources}, j.\mathit{target}, 0, i$}
  \Statex \Comment{a later constraint may need a wider target}
\EndFunction
\Function{JoinSeq}{$\mathit{sources}, \mathit{target}, k, i$} \Comment{per-source widening}
  \If{$k = \lvert \mathit{sources} \rvert$}
    \State \Return \Call{Solve}{i+1}
  \EndIf
  \State \Return \Call{Widen}{$\mathit{sources}[k], \mathit{target}, i'$}
  \Statex \Comment{$i'$ continues as \Call{JoinSeq}{$\mathit{sources}, \mathit{target}, k+1, i$}}
\EndFunction
\end{algorithmic}
```

The fast path computes the join and unifies once. It applies only when every
source is resolved, the sources have a join, and every source is coercible to it.
Otherwise, or when a later constraint fails under it (for instance an enclosing
set literal that needs a wider target), `Widen` is applied to each source in
turn, which behaves exactly like separate $\mathit{Sub}$ constraints.

## Underdetermined defaults {#underdetermined-defaults}

When the best typing still leaves a hole free, for example the element sort of an
empty container that is never used, the hole is given a default sort, so that
the equation is accepted rather than reported as underdetermined; see
[Resolving a solved node](inference/unification.md#resolving-a-solved-node).

The default is `Bool`, which is harmless, since no constraint observes the hole.
The exception is checking the equations of a template with exactly one type
variable: there the default is that type variable. A literal such as the `{}` in
`#({}) = @c0` has no variable to take its element sort from, and defaulting it to
`Bool` would fix its sort for every instance; defaulting it to the type variable
keeps it polymorphic, so that instantiation ([Type variables and polymorphic schemes, Theorem 1](polymorphism.md#thm-checking-a-template-once)) substitutes it correctly.

## The result

The typing of an equation maps every expression node to its resolved sort and
every name occurrence to the chosen overload, keyed by the node numbering of
constraint generation, which [lowering](../../rewriting/data/lowering.md) walks again.

Because the search ranks typings of the whole equation at once, it accepts some
specifications that a local algorithm rejects as ambiguous: for example, it
resolves an overloaded application by ranking an exact match above one that
needs a coercion, and it types a `whr` clause by solving all its bindings
together instead of one at a time.

## Worked examples

### An exact overload beats a coercion

```mcrl2
map  f: Nat -> Nat;
     f: Int -> Int;
var  n: Nat;
eqn  f(n) = n;
```

The argument `n` is visited before `f`, and its sort is `Nat`, the sort of its
binder. `f` becomes a two-way $\mathit{Disjunction}$, tried exhaustively:

- **`f: Nat -> Nat`**: the parameter is `Nat`, equal to the argument; the
  $\mathit{Sub}$ between them costs `0`.
- **`f: Int -> Int`**: the parameter is `Int`; equality fails, and the strict
  supersorts of `Nat` are `Int` and `Real`, of which `Int` is the first and
  succeeds, at cost `1`.

Both reach a leaf, and their measures differ in that one component, `0` against
`1`, so `Nat -> Nat` is the unique least typing and the equation is not
ambiguous. Nothing in unification prefers one branch; the comparison of measures
does.

### A literal takes its most specific sort

In `map g: Real; eqn g = 1;` the literal `1` is tried as `Pos` first. That is
consistent, because `Pos` is coercible to `Real` at the equation's join, so the
typing with `1: Pos` and a coercion at the join has a smaller measure than one
that starts the literal at `Real`.

### Containers meet at their join

In `s == t`, with `s: FSet(Pos)` and `t: Set(Pos)`, both operands share one hole.
The $\mathit{Join}$ computes $\mathit{FSet}(\mathit{Pos}) \sqcup
\mathit{Set}(\mathit{Pos}) = \mathit{Set}(\mathit{Pos})$, charges one step to
the `FSet(Pos)` source and `0` to the other, and the comparison is typed at
`Set(Pos)`.
