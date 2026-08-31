```math_preamble

\usepackage{tikz}
\usetikzlibrary{babel}
\usepackage[paperwidth=60cm,paperheight=60cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
\newcommand{\G}{\mathcal G}
\newcommand{\safe}[1]{\mathrm{safe}_{#1}(\G)}
\newcommand{\cpre}{\mathrm{cpre}}
\newcommand{\spre}{\mathrm{spre}}
\newcommand{\Attr}{\mathrm{Attr}}
\newcommand{\SAttr}{\mathrm{SAttr}}
\newcommand{\Mcpre}{\mathrm{Mcpre}}
\newcommand{\MAttr}{\mathrm{MAttr}}
\newcommand{\sMAttr}{\mathrm{sMAttr}}
```
# On-the-fly and partial solving

`merc_vpg`'s symbolic solver is based on the paper:

> Maurice Laveaux, Wieger Wesselink, Tim A.C.
Willemse, *On-The-Fly Solving for Symbolic Parity Games*, TACAS 2022, LNCS
13244, pp. 137-155,
[DOI](https://doi.org/10.1007/978-3-030-99527-0_8)

A game explored on the fly never presents the solver with a complete graph:
states and their successors are generated on demand, so at any point only a
*partial* graph $\G = (G, I)$ is available, where $I \subseteq V$ is the set
of vertices reached but not yet expanded — each may still turn out to have
successors nobody has seen yet. The four partial solvers below are not a
speed-up bolted onto a finished graph; they are how vertices get decided
*during* exploration, from whatever partial graph exists at the moment they
run. A vertex either solver declares won stays won under *every* possible
future expansion of $I$ (that soundness guarantee is Theorem 1 below), so
exploration can stop the moment the vertex the caller actually cares about —
typically the initial vertex — is decided, however small a fragment of the
full game that took.

This page derives the four solvers from the paper's definitions and lemmas
and explains how they fit together. It assumes familiarity with
[Zielonka's algorithm](zielonka.md) on symbolic parity games and does not
restate it. Every construction below is given directly in its *safe* form —
folding $I$ into every control-predecessor and attractor computation, per
§4.1 of the paper — since that is the form actually used while exploring;
each derivation marks with a `// safety: …` comment the one place this
folding happens.

## `safe_α`: the α-safe vertex set

**Definition 4.** For $\G = (G, I)$:

```math
$$
\safe\alpha = V \setminus \Attr_{\bar\alpha}(G,\, V_{\bar\alpha} \cap I)
$$
```

i.e. remove the $\bar\alpha$-attractor of $\bar\alpha$'s own incomplete vertices —
exactly the vertices from which $\bar\alpha$ could force play toward an incomplete
vertex she owns, which is where a not-yet-discovered edge could later hand her an
escape. Theorem 1 shows this is the *largest* such set: solving inside it is
sound against every future extension of $\G$ (Lemma 1), and any dominion
reaching outside it is not (Lemma 2/Corollary 1).

`safe_vertices` ports this with one addition beyond the literal formula:

```math
\begin{algorithmic}[1]
\Function{SafeVertices}{$\alpha, v, \mathit{incomplete}$}
  \State $\mathit{opponent} \gets \alpha.\Call{Opponent}{}$
  \State $V_{\mathrm{player}} \gets \Call{Players}{v}$ \Comment{$\{v \cap \text{Even-owned},\ v \cap \text{Odd-owned}\}$}
  \State $\mathit{seed} \gets (\mathit{incomplete} \cap V_{\mathrm{player}}[\mathit{opponent}]) \cup \Call{Sinks}{\mathit{incomplete}, v}$
  \State $\mathit{attracted}, \_ \gets \Call{Attractor}{\mathit{opponent}, \mathit{seed}, v, V_{\mathrm{player}}, \emptyset}$ \Comment{plain $\Attr$, Definition 4 has no incomplete set of its own here}
  \State \Return $v \setminus \mathit{attracted}$
\EndFunction
\end{algorithmic}
```

The extra `sinks(incomplete, v)` term seeds the opponent's attractor with
every *structural* sink of `incomplete` too, not only the `opponent`-owned
incomplete vertices Definition 4 literally names. An unexplored vertex has no
discovered successors yet regardless of who owns it, so without this term an
`alpha`-owned incomplete vertex with no known outgoing edges could stay
inside the returned safe set — and `partial_solve`, the one solver that runs
a plain `zielonka` over this set (below), assumes totality. The extra term is
what keeps the safe subgame actually total whenever `incomplete` is
non-empty; mCRL2's own `compute_safe_vertices` does the same for the same
reason, so this is not a merc-specific strengthening of Definition 4, just
its operational form.

## The safe attractor: `spre_α` and `SAttr_α`

Computing $\safe\alpha$ (an extra full attractor fixed point) is only worth
doing when a solver actually needs the *subgame* itself, as `partial_solve`
does. The other three solvers below only ever need attractors, never the
subgame, so §4.1 gives them a *safe* control-predecessor that folds the
incomplete set directly into $\cpre_\alpha$ instead, without ever
materialising $\safe\alpha$:

```math
$$
\spre_\alpha(\G, U) = (V_\alpha \cap \mathrm{pre}(\G, U)) \cup \big(V_{\bar\alpha} \setminus (\mathrm{pre}(\G, V\setminus U) \cup \mathrm{sinks}(\G) \cup I)\big)
$$
```

```math
$$
\SAttr_\alpha(\G, U) = \mu Z.\, U \cup \spre_\alpha(\G, Z)
$$
```

Lemma 3 shows $\spre_\alpha(\G, X)$ agrees with the ordinary $\cpre_\alpha$
computed *inside* the safe subgame for any $X \subseteq \safe\alpha$; Lemma 4
lifts this to the whole fixed point:
$\SAttr_\alpha(\G, X) = \Attr_\alpha(\G \cap \safe\alpha, X)$. This equality
is what lets every solver below use $\spre_\alpha/\SAttr_\alpha$ freely in
place of $\cpre_\alpha/\Attr_\alpha$ and stay just as sound as if it had
first restricted itself to $\safe\alpha$.

`control_predecessors` and `attractor` implement $\spre_\alpha/\SAttr_\alpha$
directly, with `incomplete` threaded through as an ordinary parameter — the
one line in each that differs from plain $\cpre_\alpha/\Attr_\alpha$ is
marked:

```math
\begin{algorithmic}[1]
\Function{ControlPredecessors}{$\alpha, u, \mathit{search\_space}, \mathit{outside}, V_{\mathrm{player}}, \mathit{incomplete}$}
  \State $\mathit{candidates} \gets \Call{Predecessors}{\mathit{search\_space}, u}$
  \State $\mathit{pulled\_in} \gets \mathit{candidates} \cap V_{\mathrm{player}}[\alpha]$
  \State $\mathit{forced} \gets (\mathit{candidates} \cap V_{\mathrm{player}}[\bar\alpha]) \setminus \mathit{incomplete}$ \Comment{safety: an unexplored $\bar\alpha$-owned vertex might still gain an escaping edge, so don't count it as forced yet}
  \ForAll{transition relations $r$}
    \State $\mathit{still\_leaving} \gets \Call{PredecessorsGroup}{r, \mathit{forced}, \mathit{outside}}$
    \State $\mathit{forced} \gets \mathit{forced} \setminus \mathit{still\_leaving}$
  \EndFor
  \State \Return $\mathit{pulled\_in} \cup \mathit{forced}$
\EndFunction
\end{algorithmic}
```

```math
\begin{algorithmic}[1]
\Function{Attractor}{$\alpha, u, v, V_{\mathrm{player}}, \mathit{incomplete}, \mathit{target}$}
  \State $Z \gets u; \quad \mathit{todo} \gets u; \quad Z_{\mathrm{outside}} \gets v \setminus Z$
  \While{$\mathit{todo} \neq \emptyset$}
    \If{$\mathit{target}$ given and $\mathit{target} \cap Z \neq \emptyset$}
      \State \Return $Z$ \Comment{early exit for $\mathrm{solve}()$}
    \EndIf
    \State $\mathit{todo} \gets \Call{ControlPredecessors}{\alpha, \mathit{todo}, Z_{\mathrm{outside}}, Z_{\mathrm{outside}}, V_{\mathrm{player}}, \mathit{incomplete}} \setminus Z$
    \State $Z \gets Z \cup \mathit{todo}$
    \State $Z_{\mathrm{outside}} \gets Z_{\mathrm{outside}} \setminus \mathit{todo}$
  \EndWhile
  \State \Return $Z$
\EndFunction
\end{algorithmic}
```

With `incomplete = ∅` the marked line vanishes and this is exactly plain
$\cpre_\alpha/\Attr_\alpha$ — `safe_vertices` above calls it that way on
purpose, since Definition 4 wants the ordinary attractor, not the safe one.
`compute_total_graph`'s two calls to `attractor` (one per player, over the
already-resolved `winning` sets) and `monotone_attractor`'s inner loop
(below) both go through this same pair of functions with the real
`incomplete` set.

## Two things the paper calls "safe"

The paper uses "safe" for two related but distinct constructions, and the
ambiguity is inherited from it, not a documentation accident:

- the **$\alpha$-safe vertex set** $\safe\alpha$ (Definition 4,
  `safe_vertices`) — a *subgame*, a subset of $V$, obtained by one extra
  attractor fixed point;
- the **safe control predecessor/attractor** (§4.1, $\spre_\alpha/\SAttr_\alpha$,
  `control_predecessors`/`attractor` above) — folding $I$ into every step so
  that no subgame ever needs to be materialised.

Lemma 4 is what makes the choice between them purely about what a given
solver already needs, not a soundness trade-off: `partial_solve` below hands
a plain, unrestricted `zielonka` an entire subgame to work on, so it needs
$\safe\alpha$ materialised regardless and uses the first form directly; the
three cycle/attractor solvers after it never need anything but attractors, so
they use $\spre_\alpha/\SAttr_\alpha$ and skip the extra fixed point
entirely.

## `partial_solve`

Port of mCRL2's `partial_solve`. This is the entry point that actually drives
solving on the fly: it is called again after each round of exploration
shrinks `incomplete`, and returns as soon as `initial_vertex` is decided —
at which point exploration itself can stop, whatever fraction of the game
remains unexplored. Internally it runs a plain `zielonka` restricted to each
player's own safe subgame in turn:

```math
\begin{algorithmic}[1]
\Function{PartialSolve}{$\mathit{epg}, \mathit{incomplete}, \mathit{partial\_solution}$}
  \State $(\mathit{winning}, \mathit{strategy}) \gets \mathit{partial\_solution}$
  \State $\mathit{total} \gets \Call{ComputeTotalGraph}{\mathit{epg}.\mathit{vertices}, \mathit{epg}.\mathit{sinks}, \mathit{winning}, \mathit{strategy}, \mathit{incomplete}}$
  \If{$\mathit{winning}$ already resolves $\mathit{epg}.\mathit{initial\_vertex}$}
    \State \Return early
  \EndIf
  \State $\mathit{safe\_even} \gets \Call{SafeVertices}{\mathrm{Even}, \mathit{total}, \mathit{incomplete}}$
  \State $\mathit{solution}_0 \gets \Call{Zielonka}{\mathit{safe\_even}}$ \Comment{plain, unrestricted zielonka on the safe subgame}
  \State $\mathit{solution}_0.\mathit{winning}[\mathrm{Even}] \gets \mathit{solution}_0.\mathit{winning}[\mathrm{Even}] \cup \mathit{winning}[\mathrm{Even}]$
  \If{$\mathit{epg}.\mathit{initial\_vertex} \in \mathit{solution}_0.\mathit{winning}[\mathrm{Even}]$}
    \State \Return $\mathit{solution}_0$ with $\mathit{winning}[\mathrm{Odd}]$ carried over unchanged
  \EndIf
  \State $\mathit{safe\_odd} \gets \Call{SafeVertices}{\mathrm{Odd}, \mathit{total}, \mathit{incomplete}}$
  \State $\mathit{solution}_1 \gets \Call{Zielonka}{\mathit{safe\_odd}}$
  \State $\mathit{solution}_1.\mathit{winning}[\mathrm{Odd}] \gets \mathit{solution}_1.\mathit{winning}[\mathrm{Odd}] \cup \mathit{winning}[\mathrm{Odd}]$
  \State $\mathit{solution}_1.\mathit{winning}[\mathrm{Even}] \gets \mathit{solution}_0.\mathit{winning}[\mathrm{Even}]$ \Comment{carry Even's result forward}
  \State \Return $\mathit{solution}_1$
\EndFunction
\end{algorithmic}
```

`zielonka` here is called on `safe_even`/`safe_odd` directly — no
$\spre_\alpha$ involved, since safety was already spent building the safe
subgame itself, per the previous section; the recursion inside runs exactly
as in [Zielonka's algorithm](zielonka.md), unmodified.

## `detect_solitair_cycles`

A solitaire cycle is a set $U$, entirely owned by one player $\alpha$, at
$\alpha$'s own priority parity, where every vertex has an edge staying inside
$U$ — so $\alpha$ can simply loop forever inside it, winning it outright with no
attractor reasoning needed at all (Proposition 1:
$C_{sol}^\alpha(\G) \subseteq \safe\alpha$ unconditionally, and the fixed
point uses only plain $\mathrm{pre}$):

```math
$$
C_{sol}^\alpha(\G) = \nu Z.\, (P_\alpha \cap V_\alpha \cap \mathrm{pre}(\G, Z))
$$
```

`detect_solitair_cycles`:

```math
\begin{algorithmic}[1]
\Function{DetectSolitaireCycles}{$\mathit{epg}, \mathit{incomplete}$}
  \State $\mathit{total} \gets \Call{ComputeTotalGraph}{\ldots}$ \Comment{+ early exit}
  \State $V_{\mathrm{player}} \gets \Call{Players}{\mathit{total}}$
  \State $\mathit{Parity} \gets \Call{Parity}{\mathit{total}}$ \Comment{$P_{\mathrm{Even}}/P_{\mathrm{Odd}}$, sinks excluded}
  \For{$\alpha \in \{\mathrm{Even}, \mathrm{Odd}\}$}
    \State $U \gets \mathit{Parity}[\alpha] \cap V_{\mathrm{player}}[\alpha]$
    \Repeat
      \State $U \gets \Call{Predecessors}{U, U}$ \Comment{plain pre --- Prop. 1: no cpre/spre anywhere in this loop}
    \Until{fixed point}
    \State \Call{AcceptCycle}{$\alpha, U, \mathit{incomplete}$}
  \EndFor
\EndFunction
\end{algorithmic}
```

The cycle search itself never asks who controls anything — a solitaire cycle
is entirely $\alpha$'s own vertices at her own priority, so there is no
adversary move to account for, and plain $\mathrm{pre}$ suffices. Safety
enters exactly once, in `accept_cycle` (shared with `detect_forced_cycles`
below), which records $U$ as won (with an overapproximate `merge(U, U)`
strategy, later cut down to real edges by `apply_strategy`) and closes it off
with a safe attractor:

```math
\begin{algorithmic}[1]
\Function{AcceptCycle}{$\alpha, U, \mathit{incomplete}$}
  \State $\mathit{attracted}, \_ \gets \Call{Attractor}{\alpha, U, \mathit{total}, V_{\mathrm{player}}, \mathit{incomplete}}$ \Comment{safety: $\SAttr_\alpha$, by Lemma 4, closes $U$ into a won region without ever computing $\safe\alpha$}
  \State $\mathit{winning}[\alpha] \gets \mathit{winning}[\alpha] \cup \mathit{attracted}$
\EndFunction
\end{algorithmic}
```

## `detect_forced_cycles`

Generalises solitaire cycles to mixed-owner cycles: $U$ may include
$\bar\alpha$-owned vertices too, as long as $\bar\alpha$ has no edge that
escapes $U$ from any of them — her "choice" to leave is illusory, so the whole
cycle is still won by $\alpha$. The direct construction restricts to the safe
subgame explicitly:

```math
$$
C_{for}^\alpha(\G) = \nu Z.\, (P_\alpha \cap \safe\alpha \cap \cpre_\alpha(\G, Z))
$$
```

and Proposition 2 gives a $\spre_\alpha$-based reformulation that never needs
$\safe\alpha$ materialised at all:

```math
$$
C_{s\text{-}for}^\alpha(\G) = \nu Z.\, (P_\alpha \cap \spre_\alpha(\G, Z)) \;=\; C_{for}^\alpha(\G)
$$
```

`detect_forced_cycles` implements the right-hand side directly — the form
that avoids the subgame — through `control_predecessors_within`
(`control_predecessors` with `outside = v \ u`):

```math
\begin{algorithmic}[1]
\Function{DetectForcedCycles}{$\mathit{epg}, \mathit{incomplete}$}
  \State $\mathit{total} \gets \Call{ComputeTotalGraph}{\ldots}$ \Comment{+ early exit}
  \State $V_{\mathrm{player}} \gets \Call{Players}{\mathit{total}}$
  \State $\mathit{Parity} \gets \Call{Parity}{\mathit{total}}$
  \For{$\alpha \in \{\mathrm{Even}, \mathrm{Odd}\}$}
    \State $U \gets \mathit{Parity}[\alpha]$
    \Repeat
      \State $U \gets U \cap \Call{ControlPredecessorsWithin}{\alpha, U, \mathit{total}, V_{\mathrm{player}}, \mathit{incomplete}}$ \Comment{safety folded in here (see \textsc{ControlPredecessors} above) --- computes $C_{s\text{-}for}^\alpha$}
    \Until{fixed point}
    \State \Call{AcceptCycle}{$\alpha, U, \mathit{incomplete}$} \Comment{same helper as \textsc{DetectSolitaireCycles}}
  \EndFor
\EndFunction
\end{algorithmic}
```

By Proposition 2 this reaches the same $U$ that restricting to $\safe\alpha$
and using plain $\cpre_\alpha$ would; it just never pays for $\safe\alpha$ to
get there.

## `detect_fatal_attractors`

Fatal attractors (Huth, Kuo, Piterman, FOSSACS 2013) find, for each priority
$c$, a set of priority-$c$ vertices that $\alpha$ (the player owning priority
$c$) can always force play back into — winning the whole attractor into that
set. The monotone control predecessor restricts candidates to priorities no
more significant than $c$ ($P_{\geq c}$ under the paper's min-parity, $P_{\leq c}$
under merc's max-parity):

```math
$$
\Mcpre_\alpha(\G, Z, U, c) = P_{\geq c} \cap \cpre_\alpha(\G, Z \cup U) \qquad
\MAttr_\alpha(\G, U, c) = \mu Z.\, \Mcpre_\alpha(\G, Z, U, c)
$$
```

```math
$$
F^\alpha(\G, c) = \nu Z.\, (P_{=c} \cap \safe\alpha \cap \MAttr_\alpha(\G \cap \safe\alpha, Z, c))
$$
```

and, again via the safe-attractor mechanism (Proposition 3):

```math
$$
F_s^\alpha(\G, c) = \nu Z.\, (P_{=c} \cap \sMAttr_\alpha(\G, Z, c)) \;=\; F^\alpha(\G, c) \quad \text{(for } c \text{ of } \alpha\text{'s own parity)}
$$
```

`detect_fatal_attractors` implements $F_s^\alpha$: $\Mcpre_\alpha/\MAttr_\alpha$
become `monotone_attractor`, which folds `incomplete` into its inner
`control_predecessors` call exactly as `attractor` does above:

```math
\begin{algorithmic}[1]
\Function{MonotoneAttractor}{$u, \alpha, c, v, V_{\mathrm{player}}, \mathit{incomplete}$}
  \State $V_c \gets \Call{VerticesWithPriorityAtMost}{v, c}$
  \State $Z \gets \emptyset; \quad \mathit{todo} \gets u; \quad Z_{\mathrm{outside}} \gets v$
  \While{$\mathit{todo} \neq \emptyset$}
    \State $\mathit{search\_target} \gets \mathit{todo} \cup u$
    \State $\mathit{outside} \gets Z_{\mathrm{outside}} \setminus u$
    \State $\mathit{pred}, \_ \gets \Call{ControlPredecessors}{\alpha, \mathit{search\_target}, v, \mathit{outside}, V_{\mathrm{player}}, \mathit{incomplete}}$ \Comment{safety folded in here too}
    \State $\mathit{todo} \gets V_c \cap (\mathit{pred} \setminus Z)$
    \State $Z \gets Z \cup \mathit{todo}$
    \State $Z_{\mathrm{outside}} \gets Z_{\mathrm{outside}} \setminus \mathit{todo}$
  \EndWhile
  \State \Return $Z$
\EndFunction
\end{algorithmic}
```

and loops over priorities in **ascending** order — merc's mirror of the
paper's descending, least-to-most-significant $\mathrm{solB}^-$ loop — running
for each the $X$/$Y$/$Z$ fixed point that finds a fatal attractor at that
priority or concludes there isn't one:

```math
\begin{algorithmic}[1]
\Function{DetectFatalAttractors}{$\mathit{epg}, \mathit{incomplete}, w_0, w_1$}
  \State $\mathit{winning} \gets [w_0, w_1]$
  \State $\mathit{total} \gets \Call{ComputeTotalGraph}{\ldots}$ \Comment{+ early exit}
  \State $V_{\mathrm{player}} \gets \Call{Players}{\mathit{total}}$
  \For{$(c, \mathit{block}) \in \mathit{game}.\Call{Priorities}{}$} \Comment{ascending under max-parity}
    \State $\alpha \gets \Call{PlayerOfPriority}{c}$
    \State $X \gets \mathit{block}; \quad Y \gets \emptyset$
    \While{$X \neq \emptyset$ and $X \neq Y$}
      \State $Y \gets X$
      \State $Z \gets \Call{MonotoneAttractor}{X, \alpha, c, \mathit{total}, V_{\mathrm{player}}, \mathit{incomplete}}$
      \If{$Z \supseteq X$}
        \State $\mathit{attracted}, \_ \gets \Call{Attractor}{\alpha, Z, \mathit{total}, V_{\mathrm{player}}, \mathit{incomplete}}$ \Comment{safety: $\SAttr_\alpha$ closes the fatal attractor into $\mathit{winning}[\alpha]$}
        \State $\mathit{winning}[\alpha] \gets \mathit{winning}[\alpha] \cup \mathit{attracted}$
        \State \textbf{break}
      \EndIf
      \State $X \gets X \cap Z$
    \EndWhile
  \EndFor
  \State \Return $\mathit{winning}$
\EndFunction
\end{algorithmic}
```

Unlike the other three solvers, this one accumulates no strategy across
iterations at all: a vertex can belong to fatal attractors at *different*
priorities on different outer-loop iterations before it is finally claimed,
and no attempt is made to reconcile that history into one strategy.
