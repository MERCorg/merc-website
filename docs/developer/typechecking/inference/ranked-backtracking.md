```math_preamble

\usepackage{algpseudocode}
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
```
# Ranked Backtracking

[Sort inference](../sort-inference.md) is a constraint-based inference built
from three layers, each unaware of the one above it:

1. A **generator** walks the expression once and emits an ordered list of
   constraints over *holes* — unknowns standing for the sort of each
   sub-expression. A fact that must hold in every solution is enforced
   immediately instead, so violating it is a direct error rather than a
   failed search.
2. A **unifier** decides equality between terms that may still contain holes,
   binding holes where needed, and can snapshot and roll back those bindings;
   see [The Unifier](unification.md).
3. A **solver** searches for an assignment that satisfies every constraint.
   Some constraints admit several *resolutions* — which overload a name
   refers to, how far a value is widened — so the solver backtracks over
   them. Because the language must pick *the best* typing rather than just
   *a* typing, every complete solution is scored and only the minimum is kept.

This page describes the solver in general terms: the search, its ranking, and
the two ways a constraint's resolutions are tried, and states why the search
returns the best typing (Theorems 1 to 3). The concrete constraint kinds of sort
inference, and how each one is discharged and scored, are [Sort inference, Definitions 3 and 4](../sort-inference.md#def-constraints).

## The search

The search walks the constraints left to right, discharging the one at index $i$ and
recursing into $i+1$. Reaching the end of the list is a *leaf*: a complete,
self-consistent solution.

```math algorithm
\begin{algorithmic}[1]
\Function{Solve}{$i$}
  \If{\Call{Dominated}{}}
    \State \Return \textsc{false} \Comment{this branch can no longer win}
  \EndIf
  \If{$i = n$}
    \State \Call{Leaf}{}
    \State \Return \textsc{true} \Comment{score this solution}
  \EndIf
  \State \Return \Call{Discharge}{$\mathit{constraints}[i], i$} \Comment{constraint-specific}
\EndFunction
\end{algorithmic}
```

Every `Discharge` is built from the same step: snapshot the unifier, apply one
resolution, and if it unifies, record its cost and continue with the rest of
the list; either way, roll back before trying anything else.

```math algorithm
\begin{algorithmic}[1]
\Function{Try}{$r, \mathit{cost}, i$}
  \State $s \gets \Call{Snapshot}{}$
  \State $\mathit{found} \gets \textsc{false}$
  \If{\Call{Apply}{$r$}} \Comment{one or more unifications}
    \State push $\mathit{cost}$ onto \textit{measure}, if any
    \State $\mathit{found} \gets \Call{Solve}{i+1}$
    \State pop \textit{measure}
  \EndIf
  \State \Call{RollbackTo}{$s$}
  \State \Return $\mathit{found}$
\EndFunction
\end{algorithmic}
```

Constraints are solved in generation order, not grouped by kind, so the
generator controls what is known when a choice is made. Emitting the most
informative constraints first — in sort inference, an application's
arguments before the applied function — means most resolutions of a later
choice fail on their first unification.

## The measure

The `measure` is a vector of small integers built up along the current
branch: a costed resolution pushes its cost, usually one component (`0` for
the cheapest), though one resolution may stand for several costs at once.
Measures are compared **lexicographically**, with the earliest constraint
most significant, and the leaf with the smallest measure wins. A resolution
that is a pure selection, with no inherent cost, pushes nothing.

What a cost means is up to the constraint kind. In sort inference it measures
how far a sort is from the most specific one admissible, so the minimum
measure is the most specific typing: equality beats a coercion, a near
coercion beats a far one.

## Trying resolutions {#trying-resolutions}

A constraint's resolutions are tried in one of two ways:

- **Exhaustive** — try every resolution, even after one succeeded. This is
  required for pure selections, where two different resolutions can reach
  leaves with equal measures: that tie must be reported as an ambiguity,
  not settled by whichever ran first.
- **First success** — try resolutions in ascending cost and stop at the first
  one whose continuation succeeds. This is safe when costs are distinct and
  ordered by construction: the component pushed here is more significant
  than any pushed later, so no costlier resolution here can produce a
  smaller measure, whatever the rest of the search does.

```math algorithm
\begin{algorithmic}[1]
\Function{Exhaustive}{$\mathit{resolutions}, i$}
  \State $\mathit{found} \gets \textsc{false}$
  \For{$r \in \mathit{resolutions}$}
    \State $\mathit{found} \gets \Call{Try}{r, \varnothing, i} \lor \mathit{found}$ \Comment{no early return}
  \EndFor
  \State \Return $\mathit{found}$
\EndFunction
\Function{FirstSuccess}{$\mathit{resolutions}, i$}
  \For{$(\mathit{cost}, r) \in \mathit{resolutions}$} \Comment{ascending cost}
    \If{\Call{Try}{$r, \mathit{cost}, i$}}
      \State \Return \textsc{true}
    \EndIf
  \EndFor
  \State \Return \textsc{false}
\EndFunction
\end{algorithmic}
```

Because `Try` recurses into the *rest* of the list before returning, "first
success" means first success of the entire remaining search, not of this one
constraint in isolation: if a later constraint fails under a cheap resolution
here, the search backtracks and retries with a costlier one.

<a id="thm-first-success-is-exact"></a>**Theorem 1 (first success is exact).** If the resolutions of a constraint have
distinct costs and are tried in ascending cost, then stopping at the first one
whose continuation reaches a leaf does not change the least measure that the
search finds.

*Proof idea.* The component pushed for this constraint precedes every component
pushed by later constraints, so in the lexicographic order every leaf below a
cheaper resolution is smaller than every leaf below a costlier one.

## Branch-and-bound

```math algorithm
\begin{algorithmic}[1]
\Function{Dominated}{}
  \If{$\mathit{best} = \varnothing$}
    \State \Return \textsc{false}
  \EndIf
  \State \Return $\mathit{measure} > \mathit{best.measure}[0 \,.\,.\, \lvert \mathit{measure} \rvert]$ \Comment{compare the prefix so far}
\EndFunction
\end{algorithmic}
```

Exhaustive choice points push no measure component, so without pruning an
expression with several independent choices would explore every
*combination* to a full leaf — exponential in the number of choices. The
pruning is exact, not a heuristic: earlier components dominate the
lexicographic order, so a prefix that is already strictly worse can never
catch up. It changes how much of the tree is visited, never which solution
wins.

<a id="thm-pruning-is-exact"></a>**Theorem 2 (pruning is exact).** Pruning the branches for which `Dominated`
holds does not change the least measure found, nor whether it is reached by two
leaves.

*Proof idea.* Measures are extended only at the end, so every leaf below a branch
has the branch's measure as a prefix; if that prefix is already larger than the
corresponding prefix of the best measure, so is every such leaf.

## Leaves and ambiguity

```math algorithm
\begin{algorithmic}[1]
\Function{Leaf}{}
  \If{$\mathit{best} = \varnothing$ \textbf{or} $\mathit{measure} < \mathit{best.measure}$}
    \State $\mathit{best} \gets \Call{Extract}{}$ \Comment{strictly better}
  \ElsIf{$\mathit{measure} = \mathit{best.measure}$}
    \State $\mathit{best.duplicate} \gets \textsc{true}$ \Comment{tie: ambiguous}
  \EndIf
\EndFunction
\end{algorithmic}
```

A leaf with a larger measure cannot reach `Leaf`, since `Dominated` would
already have pruned it. `Extract` reads the solution — every hole resolved
through the unifier, plus every committed selection — and must run *before*
the search unwinds through the snapshots that produced those bindings. A hole
that no constraint ever pinned down is filled with a default rather than
rejecting the solution; for sort inference see [Underdetermined
defaults](../sort-inference.md#underdetermined-defaults).

<a id="thm-outcome-of-the-search"></a>**Theorem 3 (outcome of the search).** When the search finishes, exactly one of
the following holds:

1. no leaf was reached, and the constraints have no solution;
2. two different leaves have the least measure, and the expression is ambiguous;
3. exactly one leaf has the least measure, and it is the result.

*Proof idea.* Every leaf that pruning removes has a larger measure than some leaf
that is kept (Theorem 2), and the resolutions that first success skips cannot
contain a smaller leaf (Theorem 1), so `Leaf` sees every leaf of least measure.

These theorems are argued on paper here; they are not formalised in Lean.
