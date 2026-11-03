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
# Exponential lower bounds for strategy improvement

[Strategy improvement](strategy-improvement.md) needs polynomially many steps per iteration, but
the number of iterations depends on the improvement rule. This page states the known exponential
lower bounds and shows how they are built: as binary counters made of gadgets. It covers
Friedmann's construction for switch-all in detail, with the trace of one increment, states the lower
bound for symmetric strategy improvement, and explains why the hybrid rule
([H-B](hybrid-strategy-improvement.md)) escapes Friedmann's counter. The definitions used here
(games and winning, play values, best responses, improving edges) are
[Parity games, Definitions 1 to 9](parity_games.md#def-parity-game) and
[Strategy improvement, Definitions 1 to 7](strategy-improvement.md#def-relevance-order).

## Binary counters {#binary-counters}

Lower bounds for strategy improvement are built as **binary counters** [Fri11], see
[Hybrid strategy improvement (H-B), Definition 10](hybrid-strategy-improvement.md#def-gadget-bit-counter). A *gadget* is a small
subgame with a designed role. A *bit* is a gadget that is either set or unset. With $k$ bits, the
algorithm is made to pass through all $2^k$ counter states. Two properties are needed:

- **(T1) gating:** bit $i$ is not set before all lower bits are set;
- **(T2) reset:** setting bit $i$ unsets all lower bits, which are then set again one by one.

<a id="thm-friedmann"></a>**Theorem 1 (Friedmann [Fri11b], Theorem 6.14).** There is a family of games $G_n$, with $n$ bits
and $10n + 4$ vertices, on which strategy improvement with the switch-all rule ([Strategy improvement, Definition 7](strategy-improvement.md#def-improving-edges)),
started from a designated initial strategy, takes at least $2^n$ iterations.

The rest of this section and the next explain the family $G_n$ of [Fri11b], Section 6. Below,
circles are Even's vertices, boxes are Odd's, and the small numbers are priorities.

**No play ever cycles.** The sink $x$ has the odd priority 1 and a self-loop. In every iteration,
every play of $(\sigma, \bar\sigma)$ ends in $x$, so Odd wins every vertex, and the whole
construction lives in the *paths* to $x$, that is, in the sets $B$ of the play values. The graph has
cycles: the bits below, and paths through the spine. But no play of the current profile stays on
one, because Odd always escapes. Such runs are called *sink runs* ([Hybrid strategy improvement (H-B), Definition 4](hybrid-strategy-improvement.md#def-sink-runs)).

## The pieces

**A bit is a simple cycle** $d_i \rightleftarrows e_i$, with even maximum $e_i$. Bit $i$ is *set*
when $\sigma(d_i) = e_i$.

```math
\begin{tikzpicture}[
  >=stealth, thick,
  ev/.style={draw, circle, minimum size=1.15cm, inner sep=1pt, align=center, font=\small},
  od/.style={draw, rectangle, minimum size=1.0cm, inner sep=2pt, align=center, font=\small},
  ext/.style={draw, dashed, rounded corners=4pt, inner sep=4pt, align=center, font=\small},
  pr/.style={font=\scriptsize}
]
\node[ev] (s) at (0,4.2) {$s$\\[-2pt]{\scriptsize $8n{+}6$}};
\node[ev] (r) at (5,4.2) {$r$\\[-2pt]{\scriptsize $8n{+}8$}};
\node[od] (f) at (2.5,2.1) {$f_i$\\[-2pt]{\scriptsize $8n{+}4i{+}7$}};
\node[ev] (g) at (5,2.1) {$g_i$\\[-2pt]{\scriptsize $4i{+}2$}};
\node[ev] (d) at (0,0) {$d_i$\\[-2pt]{\scriptsize $4i{-}1$}};
\node[od] (e) at (2.5,0) {$e_i$\\[-2pt]{\scriptsize $4i$}};
\node[od] (h) at (5,0) {$h_i$\\[-2pt]{\scriptsize $8n{+}4i{+}8$}};
\node[ev] (k) at (7.8,0) {$k_i$\\[-2pt]{\scriptsize $8n{+}4i{+}5$}};
\node[od] (x) at (10.4,0) {$x$\\[-2pt]{\scriptsize $1$}};
\node[ext] (lane) at (-3.2,0) {lane entries\\$a_1, \dots, a_{2i}$};
\node[ext] (hi) at (7.8,2.1) {$g_j$, $j > i$\\(higher bits)};
\draw[->] (d) to[bend left=25] (e);
\draw[->] (e) to[bend left=25] (d);
\draw[->] (e) -- (h);
\draw[->] (h) -- (k);
\draw[->] (k) -- (x);
\draw[->] (k) -- (hi);
\draw[->] (f) -- (e);
\draw[->] (g) -- (f);
\draw[->] (g) -- (k);
\draw[->] (s) -- (f);
\draw[->] (r) -- (g);
\draw[->] (d) -- (s);
\draw[->] (d) to[out=75, in=185] (r);
\draw[->] (d) -- (lane);
\draw[->] (x) edge[loop right] (x);
\node[pr, align=right, anchor=east] at (-0.75,4.2) {$s$ also has edges\\to $x$ and every $f_j$};
\node[pr, align=left, anchor=west] at (5.75,4.2) {$r$ also has edges\\to $x$ and every $g_j$};
\node[pr, align=center] at (1.25,-1.05) {the bit: simple cycle $d_i \rightleftarrows e_i$};
\end{tikzpicture}
```

- **Setting.** When Even closes $d_i \to e_i$, staying on the cycle would let Even win, so Odd
  escapes at $e_i$ to $h_i$. That vertex has a very high even priority, so every play through a set
  bit picks up a large reward.
- **Access.** $g_i \to f_i \to e_i$ leads into the bit, and $k_i$ continues to the next higher bits.
  The two *spine* vertices $s$ and $r$ point at the access of the most significant set bit.

**The deceleration lane implements (T1).**

```math
\begin{tikzpicture}[
  >=stealth, thick,
  ev/.style={draw, circle, minimum size=1.05cm, inner sep=1pt, align=center, font=\small},
  od/.style={draw, rectangle, minimum size=0.95cm, inner sep=2pt, align=center, font=\small},
  ext/.style={draw, dashed, rounded corners=4pt, inner sep=4pt, align=center, font=\small},
  pr/.style={font=\scriptsize}
]
\node[ev] (c) at (0,0) {$c$\\[-2pt]{\scriptsize $8n{+}4$}};
\foreach \j/\p in {1/{4n{+}3}, 2/{4n{+}5}, 3/{4n{+}7}} {
  \node[ev] (t\j) at (2.4*\j,0) {$t_{\j}$\\[-2pt]{\scriptsize $\p$}};
}
\node (dots) at (9.6,0) {$\cdots$};
\node[ev] (tm) at (12,0) {$t_{2n}$\\[-2pt]{\scriptsize $8n{+}1$}};
\foreach \j/\p in {1/{4n{+}4}, 2/{4n{+}6}, 3/{4n{+}8}} {
  \node[od] (a\j) at (2.4*\j,2) {$a_{\j}$\\[-2pt]{\scriptsize $\p$}};
  \draw[->] (a\j) -- (t\j);
}
\node[od] (am) at (12,2) {$a_{2n}$\\[-2pt]{\scriptsize $8n{+}2$}};
\draw[->] (am) -- (tm);
\draw[->] (t1) -- (c);
\draw[->] (t2) -- (t1);
\draw[->] (t3) -- (t2);
\draw[->] (dots) -- (t3);
\draw[->] (tm) -- (dots);
\node[ext] (sr) at (6,-2.4) {$s$ and $r$ (the spine)};
\draw[->] (c) |- (sr);
\foreach \j in {1,2,3} { \draw[->, dashed] (t\j) -- (sr); }
\draw[->, dashed] (tm) |- (sr);
\node[ext] (d) at (6,4) {$d_i$ has edges to $a_1, \dots, a_{2i}$};
\foreach \j in {1,2,3} { \draw[->] (d) -- (a\j); }
\draw[->] (d) -| (am);
\node[pr, align=left] at (14.3,-1.2) {every $t_j$\\also has edges\\to $s$ and $r$};
\end{tikzpicture}
```

The lane fills up one rung per iteration, from $t_1$ upwards. Each time, a new lane entry $a_j$
becomes the best-valued improving edge of $d_i$, because it carries a higher even priority than
closing the cycle at $e_i$. Switch-all takes the best-valued edge, so $d_i$ moves into the lane
instead of closing its cycle. Bit $i$ has only $2i$ lane edges, so the low bits run out of lane
entries first and close first. This delays every bit until all lower bits are set.

## One increment, as switch-all runs it

The trace of switch-all on $G_3$, from Friedmann's initial strategy, around the step from counter
state 011 to 100 (bits read as $d_3 d_2 d_1$):

| iteration | switches | bits |
|---|---|---|
| 28 | $d_3$ moves to the next lane entry ($a_6$) | 011 |
| 29 | $d_3 \to e_3$: bit 3 is closed, the lane has run out | 011 |
| 30 | $g_3 \to f_3$ and $s \to f_3$: the spine points at bit 3 | 111 |
| 31 | $r \to g_3$, $k_1, k_2 \to g_3$; the lower bits' $d_1, d_2 \to s$; the lane resets (6 switches) | 111 |
| 32 | $d_1, d_2 \to r$ and $g_1 \to k_1$, $g_2 \to k_2$: the lower cycles are open again; the lane resets again | 100 |
| 33–53 | bits 1 and 2 are solved again through the lane | 100 → 111 |

- **(T2) reset.** Once the spine points at the newly set bit $i$, the edges $d_j \to s$ and
  $d_j \to r$ of every lower bit $j$ look better under $\Xi$ than staying on the cycle, because the
  spine now leads to the reward $h_i$, which outranks every $h_j$ with $j < i$. Switch-all takes them, and the lower cycles are
  open again.
**Observation.** On $G_n$, the switch-all solver of merc (`merc-vpg solve --solver vj-si`) takes
exactly $9 \cdot 2^n - 10$ iterations, measured for $n = 1, \dots, 12$. This is consistent with
Theorem 1; it is not proved for all $n$.

## Symmetric strategy improvement is exponential too {#symmetric-strategy-improvement-is-exponential-too}

Symmetric strategy improvement [STV15] (see
[Strategy improvement](strategy-improvement.md#symmetric-strategy-improvement)) escapes Friedmann's
counter: each player only makes improving switches that agree with the best response to the
opponent's current strategy.

<a id="thm-van-dijk-loho-maat"></a>**Theorem 2 (van Dijk, Loho and Maat [vDLM24]).** There is a family of games on which symmetric
strategy improvement takes exponentially many iterations, under every rule for choosing among the
allowed switches.

Their counter lives in a *slowly improving Odd strategy*. The best response to a poor strategy can itself be poor, so the
advice it gives Even is misleading. They also note (their Appendix B) that switching at every vertex
that has an improving edge, guided by the opponent only in the choice among them, is exponential on
Friedmann's switch-best family. On that family every vertex has exactly one improving edge, so such
a rule switches exactly like switch-all.

## Why the symmetric rules escape Friedmann's counter {#why-the-symmetric-rules-escape-friedmanns-counter}

| $n$ | vertices | VJ (switch-all) | SSI | GSSI | H-B |
|---|---|---|---|---|---|
| 1 | 14 | 8 | 3 | 5 | 3 |
| 2 | 24 | 26 | 4 | 9 | 4 |
| 3 | 34 | 62 | 7 | 13 | 5 |
| 4 | 44 | 134 | 8 | 17 | 7 |
| 5 | 54 | 278 | 11 | 21 | 9 |
| 6 | 64 | 566 | 12 | 25 | 11 |

**Observation.** On $G_n$, H-B takes $2n - 1$ iterations for $3 \le n \le 6$ (the table above).

The reason is as follows. While bit $i$ is open, Odd's best response
stays on its cycle ($\bar\sigma(e_i) = d_i$). Against that, Even's best response $\sigma^*$ closes
the cycle and wins it. So $K^*$ shows the open bit as an **exploit** ([Hybrid strategy improvement (H-B), Definition 6](hybrid-strategy-improvement.md#def-exploit)), the filter at
$d_i$ keeps only $e_i$, and the lane edges no longer pass the filter there. H-B sets the bits from the
top down, one per iteration (on $G_3$: $d_3 \to e_3$, then $d_2 \to e_2$, then $d_1 \to e_1$), and it
never resets one. The lane only delays a rule that follows the current values $\Xi$. The filter
follows $K^*$, which already knows where the winning cycles are against Odd's current play.

A counter against H-B would therefore have to gate on *Odd's best response* rather than on $\Xi$.
Setting a bit would have to change $\bar\sigma$ at every lower bit, so that their cycles stop being
exploits and their edges re-open. No such reset beyond two bits has been found, see the open
[Hybrid strategy improvement (H-B), Conjecture 1](hybrid-strategy-improvement.md#conj-polynomial-iterations).

## References

| | reference |
|---|---|
| [Fri11] | O. Friedmann. *Exponential Lower Bounds for Solving Infinitary Payoff Games and Linear Programs.* PhD thesis, LMU Munich, 2011. |
| [Fri11b] | O. Friedmann. *An Exponential Lower Bound for the Latest Deterministic Strategy Iteration Algorithms.* Logical Methods in Computer Science 7(3:19), 2011. |
| [STV15] | S. Schewe, A. Trivedi and T. Varghese. *Symmetric Strategy Improvement.* ICALP 2015, Part II, LNCS 9135, pages 388–400. doi:10.1007/978-3-662-47666-6_31. arXiv:1501.06484. |
| [vDLM24] | T. van Dijk, G. Loho and M. T. Maat. *The Worst-Case Complexity of Symmetric Strategy Improvement.* CSL 2024. arXiv:2309.02223. |
