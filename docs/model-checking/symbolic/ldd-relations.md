```math_preamble
\usepackage[paperwidth=40cm,paperheight=25cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
\usepackage{amsmath}
\usepackage{amssymb}
% Default \Comment right-justifies with \hfill; keep comments inline (README.md).
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
\newcommand{\Zero}{\mathbf{0}}
\newcommand{\One}{\mathbf{1}}
\newcommand{\nd}[3]{\langle #1, #2, #3 \rangle}
\newcommand{\den}[1]{[\![ #1 ]\!]}
\newcommand{\Build}{\mathrm{build}}
\newcommand{\Spine}{\mathrm{spine}}
\newcommand{\sel}{\mathrm{sel}}
\newcommand{\Skip}{\mathsf{skip}}
\newcommand{\Read}{\mathsf{read}}
\newcommand{\Write}{\mathsf{write}}
\newcommand{\RW}{\mathsf{rw}}
```
# Relations on LDDs

Symbolic exploration in merc applies the transition groups of a model to a
set of states, and, when it learns the relation of a group on the fly,
projects the new states onto the positions that the group reads. Both
operations are part of the
`oxidd-rules-ldd` crate and are used by
[`merc_symbolic`](https://mercorg.github.io/merc/merc_symbolic/index.html).
This page defines the projection of a set of vectors and the successors of a
set of vectors under a *sparse* relation, which stores only the positions it
reads or writes, gives both algorithms, and states their correctness, which is
formalised in Lean. It assumes [List decision diagrams, Definitions 1 to
3](ldd.md#def-ldd) and the union of [List decision diagrams,
Theorem 3](ldd.md#thm-set-operations).

## Definitions

Both operations are guided per position by a description $m$ of the
positions; positions beyond the length of $m$ are dropped by a projection and
copied by a relation.

<a id="def-projection"></a>**Definition 1 (projection).** For $m \in
\{0, 1\}^*$ and a vector $x$, the projection $\sel_m(x)$ keeps the values at
the positions $i$ with $m_i = 1$:

```math
$$
\sel_{1 m}(v \cdot x) = v \cdot \sel_m(x), \qquad
\sel_{0 m}(v \cdot x) = \sel_m(x), \qquad
\sel_m(x) = \varepsilon \text{ otherwise.}
$$
```

Formalised in Lean as
[`select`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Algorithms/LDD/Relational.lean).

<a id="def-access"></a>**Definition 2 (access description).** An *access
description* is a sequence $m \in \{\Skip, \Read, \Write, \RW\}^*$, saying
whether a relation leaves a position untouched, reads it, writes it, or reads
and writes it. Its *width* $|m|_w$ counts $\Read$ and $\Write$ once and $\RW$
twice. A *relation vector* for $m$ is a vector of length $|m|_w$ that lists,
position by position, the value read and then the value written. Formalised
in Lean as
[`Access`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Algorithms/LDD/Relational.lean)
and
[`relWidth`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Algorithms/LDD/Relational.lean).

<a id="def-application"></a>**Definition 3 (application).** A relation vector
$t$ for $m$ takes $x$ to $y$, written $x \xrightarrow{t}_m y$, if $x$ and $y$
have the same length, every read position of $x$ holds the value read by $t$,
every written position of $y$ holds the value written by $t$, and every other
position of $y$, including those beyond the length of $m$, equals that of
$x$. For a set $R$ of relation vectors, $\mathrm{post}_m(X, R) = \{y \mid x
\in X, t \in R, x \xrightarrow{t}_m y\}$. Formalised in Lean as
[`Apply`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Algorithms/LDD/Relational.lean),
by recursion on $m$.

**Example 1.** A summand that reads parameters 0 and 3 and writes parameters 1
and 3 of a four-parameter process has the access description $m = \Read\,
\Write\, \Skip\, \RW$ of width 4, and its relation vectors are $t = a_0\, b_1\,
a_3\, b_3$. The vector $t = 5\,7\,0\,1$ takes $x = 5\,2\,9\,0$ to $y =
5\,7\,9\,1$.

## Algorithms

The two algorithms recurse along the spine of an LDD. For a sequence $L$ of
pairs $(v, d)$ with increasing values, $\Build(L)$ is the LDD with the spine
$L$ without the pairs whose down child is $\Zero$, so that the result is
well-formed. A recursive call on a down child consumes the first entry of
$m$; the spine itself stays at the same position.

```math algorithm
\begin{algorithmic}[1]
\Function{Project}{$m, X$}
  \If{$m = \varepsilon$} \Return $\Zero$ if $X = \Zero$, and $\One$ otherwise \EndIf
  \State $b\, m' \gets m$
  \If{$b = 1$}
    \State \Return $\Build[\, (v, \Call{Project}{m', d}) \mid (v, d) \in \Spine(X) \,]$
  \Else
    \State \Return $\bigcup \{\, \Call{Project}{m', d} \mid (v, d) \in \Spine(X) \,\}$ \Comment{by \textsc{Union}}
  \EndIf
\EndFunction
\end{algorithmic}
```

<a id="thm-projection"></a>**Theorem 1 (projection).** If $X$ is
well-formed of height $n$ and $m$ has at most $n$ entries, then
$\textsc{Project}(m, X)$ is well-formed of height equal to the number of ones
in $m$, and represents $\{\sel_m(x) \mid x \in \den{X}\}$. Proved in Lean as
[`ProjectCorrect`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Algorithms/LDD/Relational.lean).

The relational successors treat a position by its access. A read keeps the
values that both spines carry, as in an intersection. A write replaces the
value, so the tails of all values of $X$ are united once and continued below
every value that $R$ writes. A read-and-write pairs both: for each value that
$X$ and $R$ share it continues below the values that $R$ writes for it, and
since two read values can write the same value, these results are united.

```math algorithm
\begin{algorithmic}[1]
\Function{Succ}{$m, X, R$}
  \If{$m = \varepsilon$} \Return $\Zero$ if $R = \Zero$, and $X$ otherwise \EndIf
  \State $a\, m' \gets m$
  \If{$a = \Skip$}
    \State \Return $\Build[\, (v, \Call{Succ}{m', d, R}) \mid (v, d) \in \Spine(X) \,]$
  \ElsIf{$a = \Read$}
    \State \Return $\Build[\, (v, \Call{Succ}{m', d, e}) \mid (v, d) \in \Spine(X),\ (v, e) \in \Spine(R) \,]$
  \ElsIf{$a = \Write$}
    \State $U \gets \bigcup \{\, d \mid (v, d) \in \Spine(X) \,\}$ \Comment{once for all written values}
    \State \Return $\Build[\, (c, \Call{Succ}{m', U, e}) \mid (c, e) \in \Spine(R) \,]$
  \Else \Comment{$a = \RW$}
    \State \Return $\bigcup \{\, \Build[\, (c, \Call{Succ}{m', d, e'}) \mid (c, e') \in \Spine(e) \,] \mid (v, d) \in \Spine(X),\ (v, e) \in \Spine(R) \,\}$
  \EndIf
\EndFunction
\end{algorithmic}
```

The pairs $(v, d) \in \Spine(X)$, $(v, e) \in \Spine(R)$ with a common value
are found by merging the two sorted spines.

<a id="thm-successors"></a>**Theorem 2 (relational successors).** If $X$ is
well-formed of height $n$, $m$ has at most $n$ entries, and $R$ is well-formed
of height $|m|_w$, then $\textsc{Succ}(m, X, R)$ is well-formed of height $n$
and represents $\mathrm{post}_m(\den{X}, \den{R})$. Proved in Lean as
[`SuccessorsCorrect`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Algorithms/LDD/Relational.lean).

The relational predecessors, which oxidd also provides, are not covered by
this page and not formalised.

## Implementation

| definition | realised by |
|---|---|
| projection description (Definition 1) | the meta-LDD of `LDDFunction::projection_meta` |
| access description (Definition 2) | the meta-LDD of `LDDFunction::relation_meta` |
| a relation with its description | [`TransitionGroup`](https://mercorg.github.io/merc/merc_symbolic/trait.TransitionGroup.html) |

oxidd encodes a description as a singleton LDD, the *meta-LDD*, so that the
description is an LDD node and can be part of the operation-cache key, like
the operands. In the meta-LDD a read-and-write position takes two levels, its
*read half* and its *write half*, matching the two entries of the relation
vector; the write half descends $R$ but not $X$. This is the $\RW$ case
above, split over two calls.

The operands therefore do not always determine the level of the result: when
the read half of a read-and-write position consumes the last level of $X$,
the call at the write half has the terminal $\One$ for $X$, and two relations
of different shapes can end in the same nodes for $R$ and the meta-LDD at
different result levels. The operation cache of the relational successors
therefore includes the result level in its key; without it a cache hit could
return a node from the wrong level. The projection cache includes the level
as well, because projection meta-LDDs with different prefixes can share a
suffix.

The write case computes the union $U$ once per node of $X$, not once per
written value.

merc derives a transition group per group of summands from the parameters
they read and write (`SummandGrouping`). Breadth-first exploration applies
$\textsc{Succ}$ per group to the frontier, and [saturation](saturation.md)
fires an event with the same per-level step, saturating every node it builds
below the event's top position. When a relation is learned on the fly, the
projection of the frontier onto the read positions of a group, minus the
projections learned before, gives the source vectors whose successors still
have to be enumerated.
