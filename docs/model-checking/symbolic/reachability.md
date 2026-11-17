```math_preamble
\usepackage[paperwidth=40cm,paperheight=25cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
\usepackage{amsmath}
\usepackage{amssymb}
% Default \Comment right-justifies with \hfill; keep comments inline (README.md).
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
\newcommand{\Sat}{\mathrm{Sat}}
\newcommand{\Top}{\mathrm{top}}
\newcommand{\den}[1]{[\![ #1 ]\!]}
\newcommand{\Spine}{\mathrm{spine}}
\newcommand{\Build}{\mathrm{build}}
\newcommand{\post}{\mathrm{post}}
```
# Symbolic reachability

The reachability strategies of
[`merc_symbolic`](https://mercorg.github.io/merc/merc_symbolic/index.html),
selected with `--strategy` of `merc-lps explore` and `merc-sym`, compute the
states reachable from a set of initial states as an LDD. This page defines the
reachable set of a list of transition groups, gives breadth-first search,
chaining, recursive saturation and REACH, and states their correctness and
termination, which are formalised in Lean. The node-wise saturation that merc
used before is on its own page, [Saturation](saturation.md). The page assumes
[List decision diagrams](ldd.md) and [Relations on LDDs](ldd-relations.md).

## Definitions

A state is a vector of length $n$. A transition group is an *event* $e$: a
relation LDD $R_e$ over the positions it reads or writes, a meta description
$m_e$ of those positions in the sense of [Relations on LDDs,
Definition 1](ldd-relations.md#definitions), and its *top* $\Top(e)$, the first
position it reads or writes. On vectors that start at a position $p \le
\Top(e)$, the event copies the positions before $\Top(e)$; its successors of a
set $X$ are $\post_e(X)$, the relational successors of
[Relations on LDDs, Theorem 2](ldd-relations.md#thm-successors) with the meta
description extended by $\Top(e) - p$ skipped positions.

<a id="def-sat"></a>**Definition 1 (reachable set).** For a list of events
$E$, a position $p$ and a set $X$ of vectors that start at $p$, $\Sat_p(X)$ is
the smallest superset of $X$ that is closed under $\post_e$ for every
$e \in E$ with $\Top(e) \ge p$. The reachable states of $X$ are $\Sat_0(X)$.
Formalised in Lean as
[`Sat`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Algorithms/LDD/Reachability.lean).

$\Sat_p$ is the set of [Saturation, Definition 2](saturation.md#def-saturated-set).
An event with $\Top(e) > p$ copies the value at position $p$, so it acts on the
continuations below each value separately. This is the locality that saturation
and REACH exploit.

## Algorithms

All four algorithms repeat a *round* until the round changes nothing. Breadth-first
search adds $\bigcup_{e \in E} \post_e(S)$ to $S$ in one round. Chaining fires the
events one after the other, each on the result of the previous one. Both are
standard and not given in pseudocode.

**Recursive saturation** is Algorithm 1 of [vanDijk2019], without the parallel
recursion and the learning, which are discussed under
[Implementation](#implementation). $\textsc{Fire}_p(S)$ fires the events with
$\Top(e) = p$ one after the other on $S$, as chaining does.

```math algorithm
\begin{algorithmic}[1]
\Function{Saturate}{$X, p$}
  \If{$p = n$} \Return $X$ \EndIf
  \State $S \gets \Build[\, (v, \Call{Saturate}{d, p + 1}) \mid (v, d) \in \Spine(X) \,]$
  \While{$\textsc{Fire}_p(S) \ne S$}
    \State $S \gets \Build[\, (v, \Call{Saturate}{d, p + 1}) \mid (v, d) \in \Spine(\textsc{Fire}_p(S)) \,]$
  \EndWhile
  \State \Return $S$
\EndFunction
\end{algorithmic}
```

Unlike the node-wise saturation, this never changes a node in progress: the node is
rebuilt from saturated children after every round that grew it, with the ordinary
union and relational product.

**REACH** is Algorithm 3 of [Brand2023] for a relation given as a list of events,
as in the mCRL2 implementation. The paper splits one relation $R$ on the value
$i$ at the top position into the transitions $R_{ij}$ to the value $j$; those with
$i = j$ continue in the recursion below $i$. For a list of events, below the value
$v$ at position $p$ the recursion continues with the events below $p$ and with the
*diagonal* $e_v$ of every event $e$ with $\Top(e) = p$: its transitions that keep
the value $v$, as an event that starts at position $p + 1$.

```math algorithm
\begin{algorithmic}[1]
\Function{Reach}{$E, X, p$}
  \If{$p = n$} \Return $X$ \EndIf
  \State $S \gets X$
  \Repeat
    \State $S_0 \gets S$
    \State $E_v \gets [\, e \in E \mid \Top(e) > p \,] \cdot [\, e_v \mid e \in E,\ \Top(e) = p \,]$ for every value $v$
    \State $S \gets \textsc{Fire}_p(\Build[\, (v, \Call{Reach}{E_v, d, p + 1}) \mid (v, d) \in \Spine(S) \,])$
  \Until{$S = S_0$}
  \State \Return $S$
\EndFunction
\end{algorithmic}
```

## Theorems

<a id="thm-correctness"></a>**Theorem 1 (correctness).** Let every event be
well-formed for vectors of length $n$, let $X$ be a well-formed LDD of height
$n - p$, and let $\Sat_p(\den{X})$ be finite. Then breadth-first search and
chaining (for $p = 0$), recursive saturation, the node-wise saturation of
[Saturation](saturation.md) and REACH return a well-formed LDD of height
$n - p$ that represents $\Sat_p(\den{X})$. Proved in Lean as
[`BfsCorrect`, `ChainingCorrect`, `SaturateCorrect`, `SaturateNodewiseCorrect`
and `ReachCorrect`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Algorithms/LDD/Reachability.lean).

*Proof idea.* Each algorithm keeps a set $S$ with $X \subseteq S \subseteq
\Sat_p(X)$, since a round only adds successors. When a round changes nothing,
$S$ is closed under the events at $p$. For saturation and REACH, $S$ is moreover
closed under the events below $p$, because its children were saturated (or
reached) and those events copy the value at $p$. A set between $X$ and
$\Sat_p(X)$ that is closed under all events is $\Sat_p(X)$. For REACH, a
diagonal $e_v$ only has transitions of $e$, so the recursion stays within
$\Sat_p(X)$.

<a id="thm-termination"></a>**Theorem 2 (termination).** Under the hypotheses
of Theorem 1, every round that does not stop the loop of breadth-first search,
chaining, recursive saturation or REACH ends in a strictly larger set within
$\Sat_p(\den{X})$. A round of the node-wise saturation either does that or keeps
the set and removes one value from its frontier. So every loop ends, after at most
$|\Sat_p(\den{X})|$ rounds that grow the set. The recursion of saturation and
REACH ends at position $n$. Proved in Lean as
[`BfsTerminates`, `ChainingTerminates`, `SaturateTerminates`,
`SaturateNodewiseTerminates` and `ReachTerminates`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Algorithms/LDD/Reachability.lean).

The finiteness hypothesis is necessary: with an infinite reachable set, every
round adds states and none of the algorithms terminates.

The Lean model fixes the relations. The implementation learns them during the
exploration and caches results across calls; those aspects are not formalised.

## Implementation

| strategy (`--strategy`) | algorithm | where |
|---|---|---|
| `breadth-first` | breadth-first search | `merc_symbolic` |
| `chaining` | chaining | `merc_symbolic` |
| `fixpoint`, `fixpoint-chaining` | each group fired to a fixpoint before the next (not formalised) | `merc_symbolic` |
| `saturation` | recursive saturation, with learning | `saturate` of oxidd's `oxidd-rules-ldd`, driven by `merc_symbolic` |

REACH is formalised but not implemented in merc; mCRL2's `lpsreach --reach` implements
it.

**Group order.** Chaining fires the groups in list order, and so does
$\textsc{Fire}_p$ for the groups with $\Top(e) = p$; the reachable set does not
depend on the order, but the intermediate sets and the number of rounds do. The
groups are built in the order of their first summand. Saturation needs no further
order: it already fires the groups by their top, bottom-up, and fires the groups
of one level in this list order. Chaining instead sorts the groups by $\Top(e)$
from the deepest to the highest position, keeping the list order for equal tops,
so that one round of chaining works bottom-up like saturation: a group only
changes the positions from its top on, so the groups above it see states that are
already closed under the changes below. Measurements of this and other orders are
under [Symbolic benchmarks](../../benchmarks/symbolic.md#group-order).

**Learning inside saturation.** The relations of an LPS are learned on the fly.
Before firing an event at a node at its top, saturation asks the group to learn
the transitions of the projections of that node that it has not learned yet. A
result that saturation cached before a relation grew misses the new transitions,
so merc repeats the saturation with a new cache epoch until neither the states nor
the relations change; on the models measured so far this takes two passes. REACH
avoids the repetition, because its result for a node is defined by all
transitions of the events, learned or not [Brand2023].

**Parallelism.** Saturation splits the spine of a node in halves that are
saturated on different workers, until the split depth of the worker pool is used
up. Learning continues the recursion of saturation: its operations split only
where saturation still may, and every worker keeps its own enumeration context for
the whole exploration. Measurements are under
[Symbolic benchmarks](../../benchmarks/symbolic.md).

## References

- [Brand2023] S. Brand, T. Bäck, A. Laarman, *A Decision Diagram Operation for
  Reachability*, FM 2023.
- [Ciardo2001] G. Ciardo, G. Lüttgen, R. Siminiceanu, *Saturation: an efficient
  iteration strategy for symbolic state-space generation*, TACAS 2001.
- [vanDijk2019] T. van Dijk, J. Meijer, J. van de Pol, *Multi-core on-the-fly
  saturation*, TACAS 2019.
