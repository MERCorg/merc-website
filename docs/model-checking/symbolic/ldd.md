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
\newcommand{\mk}{\mathrm{mk}}
```
# List decision diagrams

A *list decision diagram* (LDD) represents a set of vectors of values
[BvdP08]. merc stores the state sets and the transition relations of its
symbolic tools as LDDs: `merc-sym` and `merc-lps` explore with them, and
[`merc_symbolic`](https://mercorg.github.io/merc/merc_symbolic/index.html)
builds on the LDD operations of the `oxidd-rules-ldd` crate of oxidd, of which
merc uses a fork. This page defines LDDs and their well-formedness, states that
well-formed LDDs are canonical, and gives the union, intersection and
difference. The projection and the relational successors are on
[Relations on LDDs](ldd-relations.md). All statements on this page are
formalised in Lean.

## Definitions

Let $V$ be a set of values with a linear order $<$. A *vector* is a finite
sequence $x \in V^*$; we write $\varepsilon$ for the empty vector and $v \cdot
x$ for the vector with first value $v$ and tail $x$.

<a id="def-ldd"></a>**Definition 1 (LDD).** The LDDs over $V$ are given by the
grammar

```math
$$
X \;::=\; \Zero \;\mid\; \One \;\mid\; \nd{v}{d}{r} \qquad (v \in V)
$$
```

The terminals $\Zero$ and $\One$ are named `Empty` and `True` in oxidd. In the
inner node $\nd{v}{d}{r}$, $v$ is the *value*, $d$ the *down child* and $r$ the
*right child*. The *spine* of $X$ is the sequence of pairs $(v, d)$ met by
following right children from $X$ until a terminal. Formalised in Lean as
[`Ldd`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Theory/LDD/Ldd.lean),
as a tree; the sharing of subdiagrams in the implementation does not change
the represented set.

<a id="def-denotation"></a>**Definition 2 (denotation).** The set of vectors
$\den{X} \subseteq V^*$ represented by $X$ is

```math
$$
\den{\Zero} = \emptyset, \qquad
\den{\One} = \{\varepsilon\}, \qquad
\den{\nd{v}{d}{r}} = \{\, v \cdot x \mid x \in \den{d} \,\} \cup \den{r}.
$$
```

Formalised in Lean as
[`Ldd.denote`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Theory/LDD/Ldd.lean).

<a id="def-well-formed"></a>**Definition 3 (well-formed).** An LDD $X$ is
*well-formed of height* $n$ if $X = \Zero$, or $X = \One$ and $n = 0$, or $X =
\nd{v}{d}{r}$, $n = k + 1$ and

1. $d \neq \Zero$ and $d$ is well-formed of height $k$,
2. $r$ is well-formed of height $n$, and
3. if $r = \nd{w}{e}{s}$ then $v < w$.

So the values on every spine strictly increase, no node has an empty down
child, and every vector in $\den{X}$ has length $n$. Formalised in Lean as
[`Ldd.WellFormed`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Theory/LDD/Ldd.lean).

Every position of a vector has its own node on every path, so the LDDs are
*quasi-reduced*: a value that is absent from a spine is not in the set, and
there is no node that stands for "any value". The consequences for saturation
are on [Saturation](saturation.md#quasi-reducedness).

**Example 1.** Let $V = \mathbb N$. The set $\{01, 02, 21\}$ of vectors of
length 2 is represented by the well-formed LDD

```math
$$
\nd{0}{\nd{1}{\One}{\nd{2}{\One}{\Zero}}}{\nd{2}{\nd{1}{\One}{\Zero}}{\Zero}}
$$
```

Its spine is $(0, \nd{1}{\One}{\nd{2}{\One}{\Zero}}),\ (2, \nd{1}{\One}{\Zero})$.
The down child of $0$ represents the tails $\{1, 2\}$ and the down child of $2$
the tail $\{1\}$.

## Canonicity

<a id="thm-canonicity"></a>**Theorem 1 (canonicity).** If $X$ and $Y$ are
well-formed of the same height and $\den{X} = \den{Y}$, then $X = Y$. Proved in
Lean as
[`Canonical`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Theory/LDD/Ldd.lean).

<a id="thm-completeness"></a>**Theorem 2 (completeness).** Every finite set of
vectors of length $n$ is represented by a well-formed LDD of height $n$.
Proved in Lean as
[`Complete`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Theory/LDD/Ldd.lean).

Together, the well-formed LDDs of height $n$ are in bijection with the finite
sets of vectors of length $n$.

*Proof idea.* For Theorem 1, the first value $v$ of a non-empty well-formed
LDD is the least first value of its vectors, $\den{d}$ is the set of tails of
the vectors that start with $v$, and $\den{r}$ is the set of the other
vectors; induction on $X$ then gives $d$ and $r$. For Theorem 2, the spine is
built from the first values in increasing order, with the down child of $v$
given by induction on $n$.

## Set operations

The three operations take two LDDs of the same height and walk their spines
in step, as a merge of two sorted lists; where both spines carry the same
value they recurse into both down children. Intersection and difference can
produce an empty down child, so they build nodes with

```math
$$
\mk(v, d, r) = \begin{cases} r & \text{if } d = \Zero \\ \nd{v}{d}{r} & \text{otherwise.} \end{cases}
$$
```

```math algorithm
\begin{algorithmic}[1]
\Function{Union}{$X, Y$}
  \If{$X = \Zero$} \Return $Y$ \EndIf
  \If{$Y = \Zero$ \textbf{or} $X = \One$} \Return $X$ \EndIf
  \State $\nd{v}{d}{r} \gets X$; \ $\nd{w}{e}{s} \gets Y$
  \If{$v < w$} \Return $\nd{v}{d}{\Call{Union}{r, Y}}$
  \ElsIf{$w < v$} \Return $\nd{w}{e}{\Call{Union}{X, s}}$
  \Else \ \Return $\nd{v}{\Call{Union}{d, e}}{\Call{Union}{r, s}}$
  \EndIf
\EndFunction
\Statex
\Function{Intersect}{$X, Y$}
  \If{$X = \Zero$ \textbf{or} $Y = \Zero$} \Return $\Zero$ \EndIf
  \If{$X = \One$} \Return $Y$ \Comment{$Y = \One$, since the heights agree} \EndIf
  \State $\nd{v}{d}{r} \gets X$; \ $\nd{w}{e}{s} \gets Y$
  \If{$v < w$} \Return $\Call{Intersect}{r, Y}$
  \ElsIf{$w < v$} \Return $\Call{Intersect}{X, s}$
  \Else \ \Return $\mk(v, \Call{Intersect}{d, e}, \Call{Intersect}{r, s})$
  \EndIf
\EndFunction
\Statex
\Function{Minus}{$X, Y$}
  \If{$X = \Zero$} \Return $\Zero$ \EndIf
  \If{$Y = \Zero$} \Return $X$ \EndIf
  \If{$X = \One$} \Return $\Zero$ \Comment{$Y = \One$} \EndIf
  \State $\nd{v}{d}{r} \gets X$; \ $\nd{w}{e}{s} \gets Y$
  \If{$v < w$} \Return $\nd{v}{d}{\Call{Minus}{r, Y}}$
  \ElsIf{$w < v$} \Return $\Call{Minus}{X, s}$
  \Else \ \Return $\mk(v, \Call{Minus}{d, e}, \Call{Minus}{r, s})$
  \EndIf
\EndFunction
\end{algorithmic}
```

The union never produces an empty down child, because the union of a
non-empty set with any set is non-empty.

<a id="thm-set-operations"></a>**Theorem 3 (set operations).** If $X$ and $Y$
are well-formed of height $n$, then $\textsc{Union}(X, Y)$,
$\textsc{Intersect}(X, Y)$ and $\textsc{Minus}(X, Y)$ are well-formed of
height $n$ and represent $\den{X} \cup \den{Y}$, $\den{X} \cap \den{Y}$ and
$\den{X} \setminus \den{Y}$. Proved in Lean as
[`UnionCorrect`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Algorithms/LDD/SetOperations.lean),
[`InterCorrect`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Algorithms/LDD/SetOperations.lean)
and
[`DiffCorrect`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Algorithms/LDD/SetOperations.lean),
for the algorithms without the operation cache and without the shortcut for
equal operands described below.

## Implementation

| definition | realised by |
|---|---|
| LDD (Definition 1) | the inner nodes and the terminals `Empty` and `True` of `oxidd-rules-ldd` |
| set of states | an LDD held by [`SymbolicLts`](https://mercorg.github.io/merc/merc_symbolic/struct.SymbolicLts.html) |
| set operations | `union`, `intsec` and `diff` of `LDDFunction` in `oxidd-rules-ldd` |

The values are `u32` indices. merc interns the values of each process
parameter in a table of its own, in the order in which exploration discovers
them, so the order $<$ on $V$ is that discovery order and not an order on the
data values. Canonicity only needs some fixed linear order per position.

Nodes are hash-consed in one unique table per level, so by Theorem 1 two
well-formed LDDs of the same height represent the same set exactly when they
are the same node. The operations use this twice. They return at once when
both operands are the same node ($X \cup X = X \cap X = X$, $X \setminus X =
\Zero$), and they store each result in an operation cache keyed by the
operation and the two operands, so a pair of shared subdiagrams is processed
once. Without the cache the recursion would follow every path and take time
exponential in the height instead of proportional to the product of the
sizes of the operands.

A node does not store its level; the caller passes the level of the result
down the recursion, and inserts each new node into the unique table of that
level. When both spines carry the same value, the two recursive calls are
independent, and with the `multi-threading` feature oxidd evaluates them in
parallel.

## References

- [BvdP08] Stefan Blom and Jaco van de Pol. *Symbolic reachability for process
  algebras with recursive data types.* Theoretical Aspects of Computing (ICTAC
  2008), LNCS 5160, pages 81 to 95. Springer, 2008.
  [doi:10.1007/978-3-540-85762-4_6](https://doi.org/10.1007/978-3-540-85762-4_6)
