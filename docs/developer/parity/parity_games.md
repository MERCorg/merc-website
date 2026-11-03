# Parity games

This page defines parity games, strategies, plays and winning, and attractors,
following Section 2 of Friedmann and Lange [FL09], as they are formalised in Lean
in the `MercLib/ParityGame` library of
[merc-verified](https://github.com/MERCorg/merc-verified) (Definitions 1 to 9).
The other pages of this section, [Strategy improvement](strategy-improvement.md),
[Exponential lower bounds](exponential-constructions.md) and
[Hybrid strategy improvement](hybrid-strategy-improvement.md), build on them and
continue their numbering. The parity game solvers of merc are in the
[`merc_vpg`](https://mercorg.github.io/merc/merc_vpg/index.html) crate.

## Games

**Definition 1 (parity game).** A parity game is $\mathcal G = (V, V_0, V_1, E,
\mathrm{pr})$ with a finite set of vertices $V$, partitioned into the vertices
$V_0$ of player Even (player $0$) and $V_1$ of player Odd (player $1$), an edge
relation $E \subseteq V \times V$ and priorities $\mathrm{pr} : V \to \mathbb N$.
The game is *total*: every vertex has a successor,
$\mathit{succ}(v) = \{w \mid (v, w) \in E\} \neq \emptyset$. A priority $n$
*favours* Even if $n$ is even and Odd otherwise. The *opponent* of player $i$ is
$\bar\imath = 1 - i$.

Priorities are max-parity, as everywhere in merc: higher priorities are more
significant. merc numbers the vertices $V = \{0, \ldots, n-1\}$, which the
strategy-improvement pages use to break ties; the Lean formalisation allows any
type of vertices, finite where an algorithm needs it.

**Definition 2 (subgame).** A set $X \subseteq V$ is a *subgame* of
$\mathcal G$ if every vertex of $X$ has a successor in $X$.

All notions below are relative to a subgame $X$, with moves that leave $X$
unavailable. This is how the subgames $\mathcal G \setminus U$ of the recursive
algorithms are represented, without constructing a new game.

## Strategies and plays

**Definition 3 (positional strategy).** A *positional strategy* is a function
$\sigma : V \to V$. Only its values at the vertices of the player it belongs to
are used.

**Definition 4 (conforming play).** A *move* in $X$ conforming to the strategy
$\sigma$ of player $i$ is an edge $(v, w) \in E$ with $v, w \in X$ and
$w = \sigma(v)$ if $v \in V_i$. A *play* is an infinite sequence of vertices
$p = p_0 p_1 p_2 \ldots$; it *conforms* to $\sigma$ in $X$ if every
$(p_k, p_{k+1})$ is such a move.

**Definition 5 (winning play).** Player $i$ *wins* the play $p$ if the greatest
priority that occurs infinitely often along $p$ favours $i$.

**Definition 6 (winning strategy).** The strategy $\sigma$ of player $i$ *wins
from* $v$ in $X$ if

1. every vertex reachable from $v$ by conforming moves has a conforming move, and
2. player $i$ wins every play from $v$ that conforms to $\sigma$ in $X$.

The first condition excludes strategies that get stuck by leaving $X$ or by
following a non-edge, for which the second would hold vacuously.

**Definition 7 (solution).** A *solution* of $X$ consists of winning regions
$W_0, W_1$ and strategies $\sigma_0, \sigma_1$ such that $W_0 \cup W_1 = X$,
$W_0 \cap W_1 = \emptyset$, and $\sigma_i$ wins from every vertex of $W_i$ in
$X$, for both players $i$.

## Attractors

**Definition 8 (attractor).** The $i$-attractor of $U$ in $X$ is
$\mathrm{Attr}_i(U) = \bigcup_k \mathrm{Attr}^k_i(U)$, with stages
$\mathrm{Attr}^0_i(U) = U$ and

```math
$$
\mathrm{Attr}^{k+1}_i(U) = \mathrm{Attr}^k_i(U) \cup \{v \in X \cap V_i \mid \exists w \in \mathrm{Attr}^k_i(U).\ (v, w) \in E\} \cup \{v \in X \cap V_{\bar\imath} \mid \forall w \in X.\ (v, w) \in E \Rightarrow w \in \mathrm{Attr}^k_i(U)\}.
$$
```

The *attractor strategy* moves a vertex of $V_i$ that first enters at stage
$k > 0$ to a successor in stage $k - 1$.

**Definition 9 (closed winning region).** A set $W$ is a *closed winning region*
of player $i$ with strategy $\sigma$ in $X$ if $W \subseteq X$, $\sigma$ moves
along an edge into $W$ from every vertex of $V_i \cap W$, every move of the
opponent from $W$ within $X$ stays in $W$, and $\sigma$ wins from every vertex of
$W$ in $X$. A *sound partial solution* of $X$ assigns each player a closed
winning region with a strategy.

Sound partial solutions are what partial solvers, such as
[fatal attractors](../symbolic/partial-solving.md#fatal-attractors), produce:
regions that are already decided, which later solving only extends.

## Theorems

**Theorem 1 (attractor).** If $X$ is a subgame and $U \subseteq X$, then
$U \subseteq \mathrm{Attr}_i(U) \subseteq X$, the complement
$X \setminus \mathrm{Attr}_i(U)$ is a subgame, no vertex of $V_i$ in the
complement has an edge into the attractor, and every play that starts in the
attractor and conforms to a strategy that agrees with the attractor strategy on
$V_i \cap (\mathrm{Attr}_i(U) \setminus U)$ reaches $U$.

**Theorem 2 (positional determinacy).** Every finite parity game has a solution
(Definition 7) with positional strategies; Zielonka's algorithm computes one.

Both theorems are proved in Lean, without `sorry`, in the
[`MercLib/ParityGame`](https://github.com/MERCorg/merc-verified/tree/main/MercLib/ParityGame) library of merc-verified. They are the same results as
Theorems 2 and 3 of the [Symbolic](../symbolic/zielonka.md) section, which apply
them to the symbolic implementation of Zielonka's algorithm.

| | Lean |
|---|---|
| Definitions 1 to 7 | `Game`, `IsSubgame`, `Strategy`, `Step`, `ConformingPlay`, `PlayWonBy`, `WinsFrom` and `Solves` |
| Definition 8 | `Game.attr` and `Game.attrStrategy` |
| Definition 9 | `Game.IsClosedWinningRegion` and `Game.SoundPartial` |
| Theorem 1 | `Game.attractorCorrect`, in the generated proofs |
| Theorem 2 | `Game.ZielonkaCorrect` |

The Lean definitions of `WinsFrom` and `Solves` (Definitions 6 and 7) are not yet
marked as reviewed in their human-vetted spec file.

## References

| | reference |
|---|---|
| [FL09] | O. Friedmann and M. Lange. *Solving Parity Games in Practice.* ATVA 2009. |
