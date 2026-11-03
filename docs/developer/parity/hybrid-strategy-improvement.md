```math_preamble
\usepackage[paperwidth=60cm,paperheight=60cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{tikz}
% Default \Comment right-justifies with \hfill.
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
\newcommand{\G}{\mathcal G}
\newcommand{\succs}{\mathit{succ}}
```
# Hybrid strategy improvement (H-B)

*Hybrid strategy improvement* (H-B) is a strategy-improvement rule that only switches edges that
are improving under the current values *and* optimal against Odd's current best response. merc
implements it in the [`merc_vpg`](https://mercorg.github.io/merc/merc_vpg/) crate as
`merc-vpg solve --solver hybrid-si`. This page assumes classic strategy improvement:
[Parity games, Definitions 1 to 9 and Theorems 1 and 2](parity_games.md#def-parity-game) and
[Strategy improvement, Definitions 1 to 7 and Theorems 1 to 3](strategy-improvement.md#def-relevance-order).
It covers, in order:

- what is new in H-B, with a worked example;
- its exact definition (Definitions 1 to 3), in pseudocode;
- the terms used in its analysis (Definitions 4 to 10), and the theorems proved about it.

How the classic rules are made exponential, and why H-B escapes those constructions, is on
[Exponential lower bounds](exponential-constructions.md).

## Reading guide

H-B is a new combination of known parts. As far as we know, no paper defines it. The papers below
cover the parts, in the order to read them.

| read | paper | what you need from it |
|---|---|---|
| **1. essential** | [VJ00] Vöge, Jurdziński: *A Discrete Strategy Improvement Algorithm for Solving Parity Games* | Everything except the filter: play values $(\lambda, B, k)$ and their order, improving switches, why improving never decreases values, why "no improving switch" means optimal, and how to compute Odd's best response (one-player game, Section 6). |
| **2. essential** | [STV15] Schewe, Trivedi, Varghese: *Symmetric Strategy Improvement* | The filter: improve only along the optimal counter-strategy to the opponent's strategy (Algorithms 3 and 5). Also why it escapes Friedmann's traps (Section 4). |
| **3. recommended** | [vDLM24] van Dijk, Loho, Maat: *The Worst-Case Complexity of Symmetric Strategy Improvement* | Why SSI is still exponential, and why that construction needs a slowly improving Odd strategy. The Discussion (the open question) and Appendix B (the per-vertex-fallback variant). |
| 4. background | [Fri11] Friedmann: PhD thesis | How strategy-improvement lower bounds are built: binary counters, snares, deceleration lanes. Needed to see what the filter defeats. Chapters on switch-all and switch-best. |
| 5. optional | [Sch08] Schewe: *An Optimal Strategy Improvement Algorithm for Solving Parity and Payoff Games* | A different global lookahead (best combination of switches), for comparison. |

## The idea of H-B

The lower bound for symmetric strategy improvement
([Exponential lower bounds for strategy improvement, Theorem 2](exponential-constructions.md#thm-van-dijk-loho-maat)) works
because Odd's strategy can be poor, so that the best response to it misleads Even. H-B removes that
weakness by never letting Odd's strategy be poor. In each iteration:

1. Odd plays its **exact best response** $\bar\sigma$ to $\sigma$, as in classic strategy
   improvement. This gives the values $\Xi$.
2. Even computes its own best response $\sigma^*$ **to $\bar\sigma$**, and its values $K^*$. $K^*(w)$ is
   how good $w$ would be for Even if Even played perfectly against the current $\bar\sigma$.
3. At each Even vertex $v$, H-B keeps the improving edges (under $\Xi$) that are also **optimal
   against $\bar\sigma$**, that is, those that maximise $K^*$ among $v$'s successors. Only vertices that
   keep such an edge switch, each to the $\Xi$-best one.

So H-B is classic strategy improvement for Even (Odd always best-responds), with SSI's filter on
Even's side. Both best responses are polynomial one-player problems. A switch is made only if it
is good both now ($\Xi$) and with full lookahead against Odd's current play ($K^*$). Throughout,
$\Xi \le K^\circ \le K^*$, where $K^\circ$ is the optimal valuation
([Theorem 6](#theorems)): $\Xi$ is a lower bound that rises, and $K^*$ an upper bound that guides.

### A worked example

Five vertices $v_0, \dots, v_4$, where $v_i$ has priority $i$, so the index is also the relevance
order. $v_3$ is Odd's; all others are Even's.

| vertex | owner | priority | successors | initial move |
|---|---|---|---|---|
| $v_0$ | Even | 0 | $v_3$ | $v_3$ |
| $v_1$ | Even | 1 | $v_2, v_4$ | $v_4$ |
| $v_2$ | Even | 2 | $v_1, v_2$ | $v_1$ |
| $v_3$ | Odd | 3 | $v_3, v_4$ | |
| $v_4$ | Even | 4 | $v_0, v_4$ | $v_0$ |

Initially every play runs $\cdots \to v_4 \to v_0 \to v_3$ and stays in Odd's self-loop on $v_3$.
That loop has odd priority 3, so everything is lost for Even. All plays have $\lambda = v_3$, and
$\bar\sigma(v_3) = v_3$ throughout. The values then differ only in the path to $v_3$:

- $v_1$, $v_2$ and $v_4$ pass $v_4$, which has even priority and is more relevant than $v_3$, so
  $B = \{v_4\}$. That is better than $v_0$'s $B = \emptyset$.
- Among plays with the same $B$, a longer path is better for Even, because $\lambda$ is odd: losing
  later is better.

Three Even vertices have improving edges:

| vertex | current | improving edge | why it looks better under $\Xi$ |
|---|---|---|---|
| $v_1$ | $v_4$ ($k = 2$) | $v_2$ ($k = 4$) | same $B$, longer path |
| $v_2$ | $v_1$ ($k = 3$) | $v_2$ itself ($k = 4$) | same $B$, longer path |
| $v_4$ | $v_0$ ($B = \emptyset$) | $v_4$ itself ($B = \{v_4\}$) | passes the even $v_4$ |

**VJ (switch-all)** makes all three switches. Then $v_4$ loops on itself (priority 4, Even
wins with $\lambda = v_4$), but $v_2$ now loops on itself too ($\lambda = v_2$, worse), and $v_1$
goes into that weaker loop. Two more iterations undo this: first $v_1 \to v_4$, then
$v_2 \to v_1$. That is **3 iterations and 5 switches**, 2 of them wasted.

**H-B** first computes $\sigma^*$, Even's best response to $\bar\sigma$. It is $v_4 \to v_4$,
$v_1 \to v_4$, $v_2 \to v_1$, which reaches $v_4$'s loop on the shortest path. So $K^*$ gives
$v_1, v_2, v_4$ the value $\lambda = v_4$ with $k = 1, 2, 0$. The filter then decides:

- $v_1$: the improving edge $v_2$ has $K^*$ with $k = 2$, but $v_4$ has $k = 0$, which is better
  for even $\lambda$. Not optimal against $\bar\sigma$, so it is dropped.
- $v_2$: the self-loop has $k = 2$, but $v_1$ has $k = 1$. Dropped.
- $v_4$: the self-loop has $\lambda = v_4$ against $\lambda = v_3$ for $v_0$. Kept.

Only $v_4 \to v_4$ is made. Now every improving edge is gone, and H-B is done after **1
iteration**. The two edges VJ took looked better only because the current values were computed
against a poor $\sigma$, which is exactly the effect Friedmann's constructions amplify.

## Relation to the literature and known bounds

H-B differs from SSI [STV15] in three ways:

1. Odd does not improve step by step but always plays the exact best response $\bar\sigma$ to
   $\sigma$. H-B is therefore not an instance of SSI: there, Odd may only make profitable
   switches that agree with $\bar\sigma$.
2. The filter allows every edge that is optimal against $\bar\sigma$ (all of
   $\operatorname{argmax} K^*$), not just the edge $\sigma^*(v)$. The tie is broken by $\Xi$.
3. If no vertex has a filtered edge, H-B falls back to switch-all. This never happens.

**No exponential lower bound for H-B is known**, as far as we know. Neither is a polynomial upper
bound (see [Conjecture 1](#theorems)). None of the known constructions applies:

- **Friedmann's lower bounds** [Fri11] lure Even into switches that look good locally. H-B's filter
  only allows switches that are optimal against $\bar\sigma$. That is a global lookahead, which
  removes this myopia: on his families H-B takes a linear number of iterations. See
  [Exponential lower bounds](exponential-constructions.md#why-the-symmetric-rules-escape-friedmanns-counter).
- **The SSI lower bound** [vDLM24] exploits that the optimal counter-strategy to a *poor* Odd
  strategy can itself be poor. In H-B, Odd's strategy is always the exact best response to
  $\sigma$, so this lure is not available. Their Discussion leaves open whether the interplay of
  the two players' strategies can be used without an exponential worst case.
- **The per-vertex-fallback variant** in [vDLM24, Appendix B] switches every improvable vertex,
  using the opponent only to choose among its improving edges. It is exponential on Friedmann's
  switch-best family. H-B switches only vertices with a filtered edge.

The worst families found so far take $\Theta(n^2)$ iterations.

## Definitions {#definitions}

The notation follows [VJ00] and [vDLM24]: $\bar\sigma$ is Odd's best response to Even's
strategy $\sigma$, $\Xi_\sigma$ (or $\Xi$) its valuation, and $\sigma^*$ is Even's best response to
$\bar\sigma$, with valuation $K^*$. [Parity games, Definitions 1 to 9](parity_games.md#def-parity-game) define games, strategies and winning, and [Strategy improvement, Definitions 1 to 7](strategy-improvement.md#def-relevance-order) define the relevance order,
profiles, play values and their order, best responses and improving edges.

<a id="def-filter"></a>**Definition 1 (filter).** Let $\sigma^*$ be Even's best response to $\bar\sigma$ and
$K^* = \Xi_{(\sigma^*, \bar\sigma)}$. The edges that are improving and optimal against $\bar\sigma$
are

```math
$\displaystyle F_\sigma(v) = \{w \in I_\sigma(v) \mid K^*(w) = \max_{x \in \succs(v)} K^*(x)\}.$
```


<a id="def-h-b-step"></a>**Definition 2 (H-B step).** Let $S = F_\sigma$ if $F_\sigma(v) \neq \emptyset$ for some $v$, and
$S = I_\sigma$ otherwise (the fallback). The next strategy is

```math
$\displaystyle \sigma'(v) = \begin{cases} \text{the first } \Xi_\sigma\text{-maximum of } S(v) & \text{if } S(v) \neq \emptyset \\ \sigma(v) & \text{otherwise.} \end{cases}$
```

VJ's switch-all step is the same with $S = I_\sigma$ always.

<a id="def-iterations-and-epochs"></a>**Definition 3 (iterations and epochs).** An *iteration* is a step in which $\sigma$ is not
optimal; the final optimality check is not counted. An *epoch* is a maximal run of consecutive
iterations with the same $\bar\sigma$.

## The H-B iteration

```math algorithm
\begin{algorithmic}[1]
\Function{HybridB}{$\G, p_0$}
  \State $p \gets p_0$ \Comment{$\sigma = p|_{V_0}$; $p|_{V_1}$ stays $p_0|_{V_1}$ throughout}
  \Loop
    \State $(\bar p, \Xi) \gets \Call{BestResponse}{p, \mathrm{Odd}}$ \Comment{$\bar\sigma = \bar p|_{V_1}$, $\Xi = \Xi_\sigma$}
    \For{$v \in V_0$}
      \State $I(v) \gets \{w \in \succs(v) \mid \Xi(w) > \Xi(p(v))\}$ \Comment{improving edges}
    \EndFor
    \If{$I(v) = \emptyset$ for every $v \in V_0$}
      \State \Return winners and strategies read off $\Xi$ and $\bar p$ \Comment{$\sigma$ is optimal}
    \EndIf
    \State $(p^*, K^*) \gets \Call{BestResponse}{\bar p, \mathrm{Even}}$ \Comment{$\sigma^* = \mathrm{BR}_{\mathrm{Even}}(\bar\sigma)$, warm start $\sigma$}
    \For{$v \in V_0$ with $I(v) \neq \emptyset$}
      \State $m \gets \max_{x \in \succs(v)} K^*(x)$
      \State $F(v) \gets \{w \in I(v) \mid K^*(w) = m\}$ \Comment{improving and optimal against $\bar\sigma$}
    \EndFor
    \If{$F(v) \neq \emptyset$ for some $v$}
      \State $S \gets F$
    \Else
      \State $S \gets I$ \Comment{fallback: never happens (Theorem 10)}
    \EndIf
    \State $q \gets p$
    \For{$v \in V_0$ with $S(v) \neq \emptyset$}
      \State $q(v) \gets$ the first $\Xi$-maximum of $S(v)$
    \EndFor
    \State $p \gets q$ \Comment{one iteration}
  \EndLoop
\EndFunction
\end{algorithmic}
```

Each pass through the loop that does not return is one *iteration* (Definition 3).

**Details that fix the run.** These choices do not affect correctness, but they decide which
strategy is reached when there are ties, and so the number of iterations:

- **Initial profile.** All three implementations start from $p_0$ ([Strategy improvement, Definition 3](strategy-improvement.md#def-profile)), the first
  successor in *relevance* order, not in file order. For experiments, `merc-vpg` can start from
  an *adversarial* profile instead (see [Statistics](#statistics)), such as the initial strategy
  of a lower-bound construction or of a counterexample found by search. H-B is correct and
  terminates from any profile, but the bounds in [Theorems](#theorems), and the open polynomial
  bound, are about runs from $p_0$.
- **Odd's warm start.** Odd's best response always starts again from Odd's moves in $p_0$ (line
  2), not from the previous $\bar\sigma$. Different warm starts can give a different $\bar\sigma$
  when there are ties. $\Xi$ does not change, but $K^*$ and the filter can.
- **$\sigma^*$'s warm start** is $\sigma$ itself (line 11 starts from $\bar p$, whose Even part is
  $\sigma$).
- **The switch** goes to the $\Xi$-best edge of $S(v)$, not the $K^*$-best one. All edges of
  $F(v)$ have the same $K^*$-value.

## Terms used in the analysis {#terms-used-in-the-analysis}

These are the terms of the analysis of H-B, collected for reference. They are not needed to run
the algorithm. $\bar\sigma_t$, $\Xi_t$, $\sigma^*_t$ and $K^*_t$ are the objects of iteration $t$,
and $K^\circ$ is the optimal valuation ([Strategy improvement, Definition 6](strategy-improvement.md#def-best-response-and-valuation)).

<a id="def-sink-runs"></a>**Definition 4 (sink runs).** A game has a *sink* $\bot$: its least relevant vertex, with odd
priority and a self-loop. A run is a *sink run* if, in every iteration, every play of
$(\sigma_t, \bar\sigma_t)$ ends in $\bot$. Then every play is a simple path into $\bot$, every
value has $\lambda = \bot$, and two values compare by their sets $B$ alone. The lower-bound
families of [Fri11] and [vDLM24] produce sink runs. The graph can still have cycles; no play of the
current profile stays on one.

<a id="def-followed-cycle-break"></a>**Definition 5 (followed cycle, break).** Let $\Gamma$ be a simple cycle whose most relevant vertex
$M$ has even priority, so a play that stays on $\Gamma$ is won by Even.

- $\Gamma$ is *followed* at $t$ if $\bar\sigma_t$ takes the $\Gamma$-edge at every Odd vertex of
  $\Gamma$.
- A *break* is an Even vertex of $\Gamma$ at which $\sigma_t$ leaves $\Gamma$.
- *Closing* a break means switching it back to its $\Gamma$-edge.

```math
\begin{tikzpicture}[
  >=stealth, thick,
  ev/.style={draw, circle, minimum size=1.0cm, inner sep=1pt, align=center, font=\small},
  od/.style={draw, rectangle, minimum size=0.9cm, inner sep=2pt, align=center, font=\small},
  ext/.style={draw, dashed, rounded corners=4pt, inner sep=4pt, align=center, font=\small},
  pr/.style={font=\scriptsize}
]
\node[ev] (M) at (90:2.2) {$M$};
\node[ev] (v1) at (18:2.2) {$v_1$};
\node[od] (o) at (-54:2.2) {$o$};
\node[ev] (v2) at (-126:2.2) {$v_2$};
\node[od] (u) at (162:2.2) {$u$};
\node[ext] (exit) at (-4.6,-3.4) {the rest of the game\\(eventually the sink $\bot$)};
\node[ext] (alt) at (4.6,-3.4) {Odd's other\\successor $a$};
\draw[->] (M) to[bend left=18] (v1);
\draw[->] (v1) to[bend left=18] (o);
\draw[->] (o) to[bend left=18] node[pr, below]{$\bar\sigma$ follows $\Gamma$} (v2);
\draw[->, densely dotted] (v2) to[bend left=18] node[pr, left, align=right]{$\Gamma$-edge, not taken:\\$v_2$ is a \emph{break}} (u);
\draw[->] (u) to[bend left=18] (M);
\draw[->] (v2) -- node[pr, below right]{$\sigma(v_2)$} (exit);
\draw[->, gray] (o) -- node[pr, right]{} (alt);
\node[pr, align=center] at (0,0) {$\Gamma$: most relevant\\vertex $M$ is even};
\node[pr, align=left, anchor=west] at (2.9,1.2) {circles: Even\\boxes: Odd\\solid: current $\sigma$ and $\bar\sigma$};
\end{tikzpicture}
```

Odd follows an open cycle because the plays leave it at a break. Once every break is closed, staying
would let Even win, so Odd leaves.

<a id="def-exploit"></a>**Definition 6 (exploit).** Iteration $t$ has an *exploit* if some $K^*_t$-value has an even
$\lambda$: the $\sigma^*_t$-play from some vertex ends in a followed Even-won cycle. In words, Odd's
current best response leaves a cycle open that Even could close and win. $\sigma^*$ closes it, and
the filter steers H-B towards it.

*Remark.* While a cycle stays followed and its edges are the unique $K^*$-optimal ones, H-B closes at
least one break per iteration, so it waits at most $|V_0|$ iterations.

<a id="def-overestimate-wrong-switch"></a>**Definition 7 (overestimate, wrong switch).** $w$ is *overestimated* if $K^*_t(w) > K^\circ(w)$:
$K^*$ promises more than Even can get against Odd's optimal play. A switch $v \to w$ is *wrong* if
some successor $u$ of $v$ has $K^\circ(u) > K^\circ(w)$.

*Remark.* Every wrong switch of H-B goes to an overestimated vertex.

<a id="def-phase-escape-opening-birth"></a>**Definition 8 (phase, escape, opening, birth).**

- A *phase* of $\Gamma$ is a maximal run of iterations in which $\Gamma$ is followed.
- An *escape* is a change of $\bar\sigma$ at an Odd vertex of a followed Even-won cycle. In a sink run,
  each exploit ends in an escape. An escape *forced* by the closing of the last break is a *forced
  escape*.
- An *opening* is a move of $\bar\sigma$ onto a cycle, which starts a new phase.
- A *birth* is an iteration in which an exploit with a given most relevant vertex $M$ appears that
  did not exist in the previous iteration. A *rebirth* is a later birth with the same $M$.

<a id="def-top-vertex-split"></a>**Definition 9 (top-vertex split).** In a sink run, let $z$ be the most relevant vertex.

- $Z_t$ is the set of vertices whose play passes $z$, and $W_t$ is the rest.
- The *good side* is the side Even prefers: $Z_t$ if $z$ has even priority, $W_t$ otherwise. The good
  side only grows.
- A *pending* vertex is an Even vertex on the bad side with an edge to the good side. A *release* is
  H-B switching a pending vertex to the good side.
- An iteration is *blocked* if there are pending vertices but no release, which happens only when
  every filtered edge of a pending vertex leads into an exploit.
- Splitting each side again at its own most relevant vertex, recursively, gives the *split tree*. A
  *progress flip* is a vertex moving to the good side of a node whose members and top are unchanged.

<a id="def-gadget-bit-counter"></a>**Definition 10 (gadget, bit, counter).** See
[Exponential lower bounds](exponential-constructions.md): a *gadget* is a
subgame with a designed role, a *bit* a gadget that is set or unset, and a *counter* a family of $k$
bits with gating (T1) and reset (T2), on which the algorithm passes through all $2^k$ states.

## Theorems {#theorems}

Let $\sigma_t$, $\Xi_t$ and $K^*_t$ be the objects of iteration $t$ of H-B, and $K^\circ$ the
optimal valuation ([Strategy improvement, Definition 6](strategy-improvement.md#def-best-response-and-valuation)). Theorems 1 to 6 are proved in Lean, without `sorry`, for
games in relevancy order ([Strategy improvement, Definition 2](strategy-improvement.md#def-relevancy-game)) and runs from $p_0$; the proofs of Theorems 7 and 8 are on
paper only.

<a id="thm-correctness"></a>**Theorem 1 (correctness).** Whenever H-B returns, the winners read off $\Xi$ are the winners of the
game.

<a id="thm-termination"></a>**Theorem 2 (termination).** H-B started from $p_0$ terminates.

H-B only switches improving edges, so termination from *any* initial profile also follows from the
termination corollary on [Strategy improvement](strategy-improvement.md#theorems); that general
form is not stated in Lean.

<a id="thm-non-empty-filter"></a>**Theorem 3 (non-empty filter).** If $\sigma$ is not optimal, then $F_\sigma(v) \neq \emptyset$ for
some $v \in V_0$ (Definition 1). So the fallback $S = I_\sigma$ of Definition 2 is never taken, and
H-B always switches along edges that are optimal against $\bar\sigma$.

<a id="thm-epoch-bound"></a>**Theorem 4 (epoch bound).** An epoch (Definition 3) has at most $|V_0|$ iterations.

<a id="thm-monotonicity"></a>**Theorem 5 (monotonicity).** $\Xi_s \le \Xi_t$ at every vertex, for all iterations $s \le t$.

<a id="thm-sandwich"></a>**Theorem 6 (sandwich).** $\Xi_s \le K^\circ \le K^*_t$ at every vertex, for all iterations $s$ and
$t$.

<a id="thm-sink-runs-without-exploits"></a>**Theorem 7 (sink runs without exploits).** A sink run (Definition 4) from $p_0$ in which no
iteration has an exploit (Definition 6) takes at most $n(n-1)/2$ iterations. *Proof idea.* The proof
splits the game at its most relevant vertex (Definition 9), recursively.

<a id="thm-progress-in-sink-runs"></a>**Theorem 8 (progress in sink runs).** In a sink run from $p_0$, every iteration makes a progress
flip in the split tree (Definition 9), and each vertex's position in the tree only improves while
its node stays the same.

<a id="conj-polynomial-iterations"></a>**Conjecture 1 (polynomial iterations).** H-B from $p_0$ takes polynomially many iterations.

No game is known on which H-B needs more than polynomially many iterations; the worst families found
so far take $\Theta(n^2)$ iterations. For sink runs, what remains open after Theorem 8 is how often
a vertex's node changes deeper than three levels down the split tree: a counter
(Definition 10) would have to make that happen exponentially often. General games, whose plays may
end in other cycles, are not covered by Theorems 7 and 6.

The Lean statements are in [`MercLib/HybridSI`](https://github.com/MERCorg/merc-verified/tree/main/MercLib/HybridSI)
of merc-verified:

| theorem | Lean |
|---|---|
| Theorem 1 | `HBCorrect` |
| Theorem 2 | `HBTerminates`, with fuel $\lvert V \rvert^{\lvert V \rvert} + 1$ for both loops |
| Theorem 3 | `FilterNonempty` |
| Theorem 4 | `EpochBound` |
| Theorem 5 | `ValuationMonotone` |
| Theorem 6 | `Sandwich`, for every saddle profile, whose valuation is $K^\circ$ |
| Conjecture 1 | `HBPolyIterations`, open |

## Statistics {#statistics}

`merc-vpg solve -v --solver hybrid-si|vj-si` logs the statistics of the run, as a readable line
and as a JSON object of key-values on the next line:

| key | meaning |
|---|---|
| `iterations` | the number of iterations (Definition 3) |
| `epochs` | the number of epochs (Definition 3) |
| `best_response_rounds` | the rounds of `BestResponse`, summed over both players |
| `fallbacks` | how often the fallback ran (always 0, by Theorem 3) |
| `time` | the time of the run in seconds, excluding the relabelling |

`--decisive-statistics` adds the decisive-element statistics. Let $\Xi_t$ be the valuation in
round $t$. Round $t$ is an *L-round* if $\lambda$ differs between $\Xi_t$ and $\Xi_{t+1}$ for
some vertex. Otherwise its decisive element $\delta_t$ is the maximum of
$B_t(v) \mathbin\triangle B_{t+1}(v)$ over all $v$, or $-1$ if there is none. $N_x$ counts the
rounds with $\delta_t = x$, and $N^I_x$ the same within one l-interval, a maximal run of non-L
rounds.

| key | meaning |
|---|---|
| `l_rounds` | the number of L-rounds |
| `max_count`, `max_count_element` | $\max_x N_x$, and the $x$ attaining it |
| `max_interval_count` | $\max_{I, x} N^I_x$ |
| `max_epoch_length` | the length of the longest epoch |
| `even_vertices` | $\lvert V_0 \rvert$ |

`--max-iterations N` stops the solver with an error after `N` iterations. For experiments,
`--initial-strategy F` starts from the moves in `F` instead of $p_0$: one `<from> <to>` (or
`<from> <name> <to> <name>`) per line, in original vertex indices, and vertices without a line
keep their move in $p_0$.

## References

| | reference |
|---|---|
| [VJ00] | J. Vöge and M. Jurdziński. *A Discrete Strategy Improvement Algorithm for Solving Parity Games.* CAV 2000, LNCS 1855, pages 202–215. |
| [STV15] | S. Schewe, A. Trivedi and T. Varghese. *Symmetric Strategy Improvement.* ICALP 2015, Part II, LNCS 9135, pages 388–400. doi:10.1007/978-3-662-47666-6_31. arXiv:1501.06484. |
| [vDLM24] | T. van Dijk, G. Loho and M. T. Maat. *The Worst-Case Complexity of Symmetric Strategy Improvement.* CSL 2024. arXiv:2309.02223. |
| [Fri11] | O. Friedmann. *Exponential Lower Bounds for Solving Infinitary Payoff Games and Linear Programs.* PhD thesis, LMU Munich, 2011. |
| [Sch08] | S. Schewe. *An Optimal Strategy Improvement Algorithm for Solving Parity and Payoff Games.* CSL 2008, LNCS 5213, pages 369–384. |
