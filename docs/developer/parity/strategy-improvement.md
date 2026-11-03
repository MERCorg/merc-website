```math_preamble
\usepackage[paperwidth=60cm,paperheight=60cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
\usepackage{amsmath}
\usepackage{amssymb}
% Default \Comment right-justifies with \hfill.
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
\newcommand{\G}{\mathcal G}
\newcommand{\succs}{\mathit{succ}}
```
# Strategy improvement

*Strategy improvement* solves a parity game by repeatedly improving a
positional strategy of one player until it is optimal [VJ00]. merc implements
it in the [`merc_vpg`](https://mercorg.github.io/merc/merc_vpg/) crate, with
the classic switch-all rule as `merc-vpg solve --solver vj-si`. This page gives
the definitions and theorems that strategy improvement rests on: play values,
best responses and improving edges (Definitions 1 to 7, Theorems 1 to 3). It
assumes parity games, strategies and winning, [Parity games, Definitions 1 to 9](parity_games.md#def-parity-game). The
[hybrid rule H-B](hybrid-strategy-improvement.md) builds on them, and
[Exponential lower bounds](exponential-constructions.md) shows how the classic
rules are forced to take exponentially many iterations. The definitions and the
theorems on H-B are formalised in Lean in
[merc-verified](https://github.com/MERCorg/merc-verified).

## Overview

Zielonka's algorithm and priority promotion work on **sets of vertices**: they
peel off attractors of the top priority and recurse. Progress measures work on
**vertex labels** that only increase. Strategy improvement works on
**strategies**. It is the parity-game version of policy iteration for Markov
decision processes, and of the simplex method.

1. **Fix** a positional strategy $\sigma$ for Even. What remains is a one-player
   game for Odd, and Odd's best response $\bar\sigma$ to it is computable in
   polynomial time ([Theorem 3](#theorems)).
2. **Evaluate.** With both strategies fixed, the play from every vertex is a
   lasso, and its *play value* $\Xi_\sigma(v)$ says how good it is for Even
   ([Definition 4](#definitions)).
3. **Improve.** An Even edge is *improving* if its target has a better value
   than the current move ([Definition 7](#definitions)).
4. **Switch** some improving edges. Values only go up
   ([Theorem 1](#theorems)), so no strategy repeats.
5. **Stop** when no edge is improving. Then $\sigma$ is optimal, and the winners
   are read off the values ([Theorem 2](#theorems)).

```math algorithm
\begin{algorithmic}[1]
\Function{StrategyImprovement}{$\G, \sigma_0, \textsc{Rule}$}
  \State $\sigma \gets \sigma_0$
  \Loop
    \State $\bar\sigma \gets$ Odd's best response to $\sigma$; \ $\Xi_\sigma \gets$ the play values of $(\sigma, \bar\sigma)$
    \State $I_\sigma \gets$ the improving edges under $\Xi_\sigma$
    \If{$I_\sigma = \emptyset$}
      \State \Return Even wins $\{v \mid \lambda(v) \text{ has even priority}\}$, with strategies $\sigma$ and $\bar\sigma$
    \EndIf
    \State $\sigma \gets \Call{Rule}{\sigma, \bar\sigma, \Xi_\sigma, I_\sigma}$ \Comment{switches only improving edges}
  \EndLoop
\EndFunction
\Statex
\Function{SwitchAll}{$\sigma, \bar\sigma, \Xi_\sigma, I_\sigma$} \Comment{VJ, \texttt{--solver vj-si}}
  \State \Return $\sigma$ with every $v$ switched to its $\Xi_\sigma$-best edge in $I_\sigma(v)$
\EndFunction
\end{algorithmic}
```

Each iteration costs a best response plus a valuation, which is polynomial. The
open question is the *number of iterations*, which depends on the
*improvement rule*: which improving edges are switched.

## Definitions {#definitions}

The notation follows [VJ00] and [vDLM24]: $\bar\sigma$ is Odd's best response
to Even's strategy $\sigma$, and $\Xi_\sigma$ (or $\Xi$) its valuation.
The definitions specific to H-B are
[Hybrid strategy improvement (H-B), Definitions 1 to 10](hybrid-strategy-improvement.md#def-filter).

Parity games $\G = (V, V_0, V_1, E, \mathrm{pr})$ with vertices
$V = \{0, \ldots, n-1\}$ and successors $\succs(v)$ are
[Parity games, Definition 1](parity_games.md#def-parity-game).

<a id="def-relevance-order"></a>**Definition 1 (relevance order).** The relevance order $\sqsubset$ is the
strict total order

```math
$\displaystyle v \sqsubset w \iff \mathrm{pr}(v) < \mathrm{pr}(w) \text{ or } (\mathrm{pr}(v) = \mathrm{pr}(w) \text{ and } v < w),$
```

the lexicographic order on $(\mathrm{pr}(v), v)$. Vertex $w$ is *more
relevant* than $v$ if $v \sqsubset w$.

<a id="def-relevancy-game"></a>**Definition 2 (relevancy game).** Let $\pi : V \to \{0, \ldots, n-1\}$ be the
unique bijection with $v \sqsubset w \iff \pi(v) < \pi(w)$. The relevancy game
of $\G$ is its isomorphic copy $\G' = (V', V'_0, V'_1, E', \mathrm{pr}')$ along
$\pi$:

```math
$\displaystyle V' = \{0, \ldots, n-1\}, \quad V'_i = \pi(V_i), \quad E' = \{(\pi(v), \pi(w)) \mid (v, w) \in E\}, \quad \mathrm{pr}' = \mathrm{pr} \circ \pi^{-1}.$
```

In $\G'$ the relevance order is the order on the indices, and $\mathrm{pr}'$ is
monotone: $i < j$ implies $\mathrm{pr}'(i) \le \mathrm{pr}'(j)$. So the most
relevant vertex of a set is its maximum. Since $\pi$ is an isomorphism, $v$ is
won by a player in $\G$ iff $\pi(v)$ is won by that player in $\G'$, and a
strategy $\sigma'$ of $\G'$ maps back to $\pi^{-1} \circ \sigma' \circ \pi$.
From here on we work in $\G'$ and drop the primes. Successor lists are sorted
by relevance and contain no duplicates, and every "first" below means first in
this order.

<a id="def-profile"></a>**Definition 3 (profile).** A *profile* $p : V \to V$ with $p(v) \in \succs(v)$
fixes one move at every vertex. It holds Even's strategy $\sigma = p|_{V_0}$ and
Odd's strategy $\tau = p|_{V_1}$. The play from $v$ under $p$ is
$v, p(v), p(p(v)), \ldots$, which is a *lasso*: a path into a cycle. The
*initial profile* is $p_0(v) = \min \succs(v)$, the first successor in
relevance order.

<a id="def-play-value"></a>**Definition 4 (play value).** The value of the play from $v$ under $p$ is the
triple $\Xi_p(v) = (\lambda, B, k)$, where

- $\lambda$ is the maximum of the cycle that the play ends in;
- $B$ is the set of vertices greater than $\lambda$ that the play visits before
  it first reaches $\lambda$;
- $k$ is the number of steps until $\lambda$ is first reached.

<a id="def-order-on-play-values"></a>**Definition 5 (order on play values).** Let
$\mathrm{reward}(\lambda) = \lambda + 1$ if $\mathrm{pr}(\lambda)$ is even and
$-(\lambda + 1)$ otherwise. Even prefers larger values and Odd smaller ones,
where $(\lambda_a, B_a, k_a) < (\lambda_b, B_b, k_b)$ is decided
lexicographically:

1. **By $\lambda$.** The larger reward is better.
2. **By $B$.** Let $d = \max(B_a \mathbin\triangle B_b)$. If $\mathrm{pr}(d)$
   is even, the set containing $d$ is better; if it is odd, the other one is.
3. **By $k$.** Shorter is better if $\mathrm{pr}(\lambda)$ is even, longer if
   it is odd.

Equivalently, the value is the integer triple
$\bigl(\mathrm{reward}(\lambda),\ \sum_{x \in B} \mathrm{sgn}(x)\, 2^x,\ \mp k\bigr)$
compared lexicographically, with $\mathrm{sgn}(x) = +1$ if $\mathrm{pr}(x)$ is
even and $-1$ otherwise, and $-k$ for even $\lambda$. This is a total preorder,
and two vertices have equal values exactly when their triples are equal.

<a id="def-best-response-and-valuation"></a>**Definition 6 (best response and valuation).** Odd's *best response*
$\bar\sigma$ to $\sigma$ is a strategy of Odd that minimises the play value of
every vertex against $\sigma$; Even's best response to $\tau$ is defined
dually. The *valuation* of $\sigma$ is $\Xi_\sigma = \Xi_{(\sigma, \bar\sigma)}$,
which does not depend on which best response is taken. A strategy $\sigma$ is
*optimal* if $\Xi_{\sigma'} \le \Xi_\sigma$ for every $\sigma'$; the optimal
valuation is $K^\circ$.

<a id="def-improving-edges"></a>**Definition 7 (improving edges).** For $v \in V_0$, the *improving edges* are

```math
$\displaystyle I_\sigma(v) = \{w \in \succs(v) \mid \Xi_\sigma(w) > \Xi_\sigma(\sigma(v))\}.$
```

The *switch-all* rule (VJ) switches every $v$ with $I_\sigma(v) \neq \emptyset$
to the first $\Xi_\sigma$-maximum of $I_\sigma(v)$, and keeps $\sigma(v)$
elsewhere.

## Theorems {#theorems}

The following are the classic results of [VJ00] that make strategy improvement
correct for every improvement rule.

<a id="thm-improvement"></a>**Theorem 1 (improvement).** Let $\sigma'$ be obtained from $\sigma$ by
switching at least one vertex $v$ to an edge in $I_\sigma(v)$, and keeping
$\sigma$ elsewhere. Then $\Xi_{\sigma'} \ge \Xi_\sigma$ at every vertex, and
$\Xi_{\sigma'} \neq \Xi_\sigma$.

<a id="thm-optimality"></a>**Theorem 2 (optimality).** $\sigma$ is optimal iff $I_\sigma(v) = \emptyset$
for every $v \in V_0$. In that case Even wins exactly the vertices $v$ whose
$\Xi_\sigma(v)$ has a $\lambda$ of even priority, and $\sigma$ and $\bar\sigma$
are winning strategies for Even and Odd on their winning regions.

**Corollary (termination).** Strategy improvement terminates for every
improvement rule that switches only improving edges, after at most as many
iterations as there are positional strategies for Even. *Proof.* By
Theorem 1 the valuations strictly increase, so no strategy repeats; by
Theorem 2 the loop only stops at an optimal strategy.

<a id="thm-one-player-best-response"></a>**Theorem 3 (one-player best response).** In a game where all moves of one
player $Q$ are fixed by $p$, the moves of the other player $P$ in $p$ form a
best response iff no vertex $v \in V_P$ has a successor whose $\Xi_p$-value is
strictly better for $P$ than that of $p(v)$. Such a best response is reached in
polynomial time by one-player switch-all ([VJ00] Section 6).

Theorem 3 is what [`BestResponse`](#best-responses) below relies on.

## Improvement rules and their worst case

Switch-all is the usual rule. Friedmann [Fri11] built games on which
switch-all, switch-best and the other standard rules need exponentially many
iterations ([Exponential lower bounds for strategy improvement, Theorem 1](exponential-constructions.md#thm-friedmann)). The
trick is always the same: a vertex sees an edge that looks better under the
*current* values, which are computed against the current, poor $\sigma$. It
switches there, and that switch has to be undone later.

### Symmetric strategy improvement {#symmetric-strategy-improvement}

Schewe, Trivedi and Varghese [STV15] use the opponent's view to choose better
switches. They keep a strategy for each player, $\sigma$ and $\tau$, and the
optimal counter-strategy to each: $\bar\sigma$, Odd's best response to
$\sigma$, and $\bar\tau$, Even's best response to $\tau$. Even then only makes
improving switches that agree with $\bar\tau$, and Odd only those that agree
with $\bar\sigma$. Following $\bar\tau$ steers away from Friedmann's traps,
because it knows where the good cycles for Even are against Odd's play.

Van Dijk, Loho and Maat [vDLM24] showed that symmetric strategy improvement
(SSI) is still exponential, for any rule of which allowed switches to take
([Exponential lower bounds for strategy improvement, Theorem 2](exponential-constructions.md#thm-van-dijk-loho-maat)).
Their construction keeps Odd's strategy $\tau$ *poor*: the optimal
counter-strategy to a poor strategy can itself be poor, and so steer Even into
a trap of its own.

## Computing a valuation

The vertices whose plays share the cycle maximum $\lambda$ form a tree rooted at
$\lambda$. All vertices of the cycle are identified with the root, and the
parent of every other vertex $x$ is $p(x)$. The depth of $x$ is its number of
steps to the cycle, zero on the cycle. $B(v)$ is then the set of vertices
greater than $\lambda$ on the tree path from $v$ to the root, excluding it. For
two vertices in the same tree, the most relevant vertex of
$B_a \mathbin\triangle B_b$ is the maximum over the two paths up to their lowest
common ancestor. With binary lifting this takes $O(n \log n)$ preprocessing per
valuation, and $O(\log n)$ per comparison.

```math algorithm
\begin{algorithmic}[1]
\Function{Valuation}{$p$}
  \For{every unvisited $s \in V$}
    \State follow $s, p(s), p(p(s)), \ldots$ until a vertex $u$ is visited twice or was evaluated before
    \If{$u$ closes a new cycle $C$}
      \State $\lambda \gets \max C$
      \For{$x \in C$}
        \State $\lambda(x) \gets \lambda$; \ $k(x) \gets$ distance from $x$ to $\lambda$ along $C$; \ $\mathit{depth}(x) \gets 0$; \ $\mathit{up}(x) \gets \lambda$
      \EndFor
    \EndIf
    \For{the remaining path vertices $x$, from the last one back to $s$} \Comment{$y = p(x)$ is evaluated}
      \State $\lambda(x) \gets \lambda(y)$; \ $k(x) \gets k(y) + 1$; \ $\mathit{depth}(x) \gets \mathit{depth}(y) + 1$
      \State $\mathit{up}(x) \gets y$ if $\mathit{depth}(y) > 0$, else $\lambda(y)$
      \State $\mathit{mark}(x) \gets x$ if $x > \lambda(x)$, else none \Comment{$x \in B$ of every vertex below it}
    \EndFor
  \EndFor
  \State build binary-lifting tables of $\mathit{up}$ and of the maximum $\mathit{mark}$ on each jump
  \State \Return $\Xi = (\lambda, k, \mathit{depth}, \mathit{up}, \mathit{mark})$
\EndFunction
\Statex
\Function{Compare}{$\Xi, a, b$} \Comment{$>$ means better for Even}
  \If{$\lambda(a) \neq \lambda(b)$}
    \State \Return compare $\mathrm{reward}(\lambda(a))$ with $\mathrm{reward}(\lambda(b))$
  \EndIf
  \State $d \gets$ maximum $\mathit{mark}$ on the tree paths from $a$ and $b$ up to their lowest common ancestor
  \If{$d$ exists}
    \State \Return $a > b$ iff ($d$ is on $a$'s path) $=$ ($d$ has even priority)
  \EndIf
  \State \Return $a > b$ iff ($k(a) < k(b)$) $=$ ($\lambda(a)$ has even priority) \Comment{equal if $k(a) = k(b)$}
\EndFunction
\end{algorithmic}
```

## Best responses {#best-responses}

A best response of player $P$ is computed by one-player switch-all, which is
correct by [Theorem 3](#theorems). It is warm-started from the moves already in
the profile:

```math algorithm
\begin{algorithmic}[1]
\Function{BestResponse}{$p, P$} \Comment{only the moves of player $P$ change}
  \Loop
    \State $\Xi \gets \Call{Valuation}{p}$
    \State $\mathit{changed} \gets \mathbf{false}$
    \For{$v \in V_P$}
      \State $b \gets p(v)$
      \For{$w \in \succs(v)$, in relevance order}
        \If{$w$ is strictly better than $b$ for $P$ under $\Xi$} \Comment{Even: $>$, Odd: $<$}
          \State $b \gets w$
        \EndIf
      \EndFor
      \If{$b \neq p(v)$}
        \State $p(v) \gets b$; \ $\mathit{changed} \gets \mathbf{true}$
      \EndIf
    \EndFor
    \If{$\neg\mathit{changed}$}
      \State \Return $(p, \Xi)$ \Comment{$\Xi$ is the valuation of the returned profile}
    \EndIf
  \EndLoop
\EndFunction
\end{algorithmic}
```

The current move is kept unless some successor is strictly better. Among
equally good better successors, the first one is taken.

## In merc

The solver in [`merc_vpg`](https://mercorg.github.io/merc/merc_vpg/) first
relabels the game to its relevancy game (Definition 2), so that the relevance
order is the order on the vertex indices, and maps the strategies back
afterwards. Runs start from the initial profile $p_0$ (Definition 3). The Lean
formalisation in [merc-verified](https://github.com/MERCorg/merc-verified)
computes play values directly from Definition 4, by iterating the profile,
rather than with the tree structure above. Both give the same order
(Definition 5).

## References

| | reference |
|---|---|
| [VJ00] | J. Vöge and M. Jurdziński. *A Discrete Strategy Improvement Algorithm for Solving Parity Games.* CAV 2000, LNCS 1855, pages 202–215. |
| [STV15] | S. Schewe, A. Trivedi and T. Varghese. *Symmetric Strategy Improvement.* ICALP 2015, Part II, LNCS 9135, pages 388–400. doi:10.1007/978-3-662-47666-6_31. arXiv:1501.06484. |
| [vDLM24] | T. van Dijk, G. Loho and M. T. Maat. *The Worst-Case Complexity of Symmetric Strategy Improvement.* CSL 2024. arXiv:2309.02223. |
| [Fri11] | O. Friedmann. *Exponential Lower Bounds for Solving Infinitary Payoff Games and Linear Programs.* PhD thesis, LMU Munich, 2011. |
