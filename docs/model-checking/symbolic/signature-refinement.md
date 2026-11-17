```math_preamble
\usepackage[paperwidth=60cm,paperheight=60cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{tikz}
% Default \Comment right-justifies with \hfill; keep comments inline (README.md).
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
\newcommand{\vs}{\vec s}
\newcommand{\vb}{\vec b}
\newcommand{\B}{\mathbb B}
\newcommand{\sig}{\mathit{sig}}
\newcommand{\Refine}{\textsc{Refine}}
```
# Symbolic signature refinement

*Signature refinement* computes strong bisimilarity on a symbolic LTS by
repeatedly splitting a partition of the reachable states according to the
*signature* of each state: the set of pairs of an action and the block of a
successor. merc implements it in
[`merc_symbolic`](https://mercorg.github.io/merc/merc_symbolic/index.html) as
[`sigref_symbolic`](https://mercorg.github.io/merc/merc_symbolic/fn.sigref_symbolic.html),
following [vDvdP16], and runs it as `merc-sym reduce strong-bisim-sigref`. The
page defines how a partition is encoded as a BDD, which is shared with
[stability-based refinement](stability-refinement.md), and gives the
traversal that assigns block numbers. It assumes binary decision diagrams and
strong bisimilarity $\leftrightarrow$ as known.

## Definitions

A symbolic LTS has state variables $\vs = s_1 \dots s_n$, next-state variables
$\vs' = s'_1 \dots s'_n$, a set $R \subseteq \B^n$ of reachable states and a
transition relation $T(\vs, a, \vs')$ over the state, action and next-state
variables. We write $T_a(\vs, \vs')$ for $T$ with the action fixed to $a$.
Blocks are numbered by bit-vectors over the *block variables*
$\vb = b_0 \dots b_{m-1}$, and every variable order used below places all
state variables above all block variables.

<a id="def-partition-function"></a>**Definition 1 (partition function).** A
BDD $P(\vs, \vb)$ is a *partition function* if every $s \in R$ satisfies
$P(s, \beta)$ for exactly one $\beta \in \B^m$, and no $s \notin R$
satisfies $P(s, \beta)$ for any $\beta$. We write $\pi_P(s)$ for this
$\beta$, the *block number* of $s$, and $|P|$ for the number of distinct
block numbers of reachable states.

<a id="def-boundary-node"></a>**Definition 2 (boundary node).** Let $F(\vs,
\vec x)$ be a BDD in which all variables of $\vs$ lie above all variables of
$\vec x$. The *boundary node* $F|_s$ of a state $s \in \B^n$ is the node
reached from the root of $F$ by following the assignment $s$ on the levels
of $\vs$. It is the BDD of $\{x \mid F(s, x)\}$, so by canonicity two states
have the same boundary node if and only if they satisfy $F$ for the same set
of vectors $x$.

For a partition function the boundary node of a reachable state $s$ is the
cube $\vb = \pi_P(s)$, so boundary nodes and blocks correspond one to one.
Unreachable states all reach the terminal $0$, which is not a block. A
boundary node can lie on any level at or below the first block variable,
because reduction removes state-variable nodes the function does not depend
on.

**Example 1.** Figure 1 shows a partition function over $s_1 s_2$ and one
block variable $b_0$, with $R = \{00, 01, 10\}$, $\pi_P(00) = 0$ and
$\pi_P(01) = \pi_P(10) = 1$. The two $b_0$ nodes are the boundary nodes of
the two blocks, and state $11$ reaches the terminal $0$. Dashed edges are
the $0$-edges.

```math
\begin{tikzpicture}[
  >=stealth, thick,
  v/.style={draw, circle, minimum size=0.8cm, inner sep=1pt, font=\small},
  t/.style={draw, rectangle, minimum size=0.6cm, font=\small},
  lo/.style={->, dashed},
  hi/.style={->},
  lbl/.style={font=\scriptsize}
]
\node[v] (r) at (0,0) {$s_1$};
\node[v] (a) at (-1.6,-1.4) {$s_2$};
\node[v] (b) at (2.6,-1.4) {$s_2$};
\node[v] (n0) at (-1.6,-3.0) {$b_0$};
\node[v] (n1) at (0.4,-3.0) {$b_0$};
\node[t] (one) at (-0.8,-4.5) {$1$};
\node[t] (zero) at (2.6,-4.5) {$0$};
\draw[lo] (r) -- (a);
\draw[hi] (r) -- (b);
\draw[lo] (a) -- (n0);
\draw[hi] (a) -- (n1);
\draw[lo] (b) -- (n1);
\draw[hi] (b) -- (zero);
\draw[lo] (n0) -- (one);
\draw[hi] (n0) -- (zero);
\draw[lo] (n1) -- (zero);
\draw[hi] (n1) -- (one);
\draw[gray, densely dotted] (-3.2,-2.25) -- (3.6,-2.25) node[right, lbl, black] {boundary};
\node[lbl, left] at (n0.west) {block $0$};
\node[lbl, right] at (n1.east) {block $1$};
\end{tikzpicture}
```

<a id="def-signature"></a>**Definition 3 (signature).** The *signature* of
a state $s$ with respect to a partition function $P$ is
$\sig_P(s) = \{(a, \pi_P(s')) \mid T_a(s, s')\}$. Symbolically it is the BDD

```math
$$
\sigma_P(\vs, a, \vb) = \exists \vs'.\ T(\vs, a, \vs') \wedge P(\vs', \vb),
$$
```

where $P(\vs', \vb)$ is $P$ with $\vs$ renamed to $\vs'$, so that
$\sig_P(s) = \{(a, \beta) \mid \sigma_P(s, a, \beta)\}$. Formalised in Lean
as
[`StrongSignature`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Theory/Signatures/Signature.lean).
A partition is *stable* if states with the same block number have the same
signature, formalised as
[`IsStable`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Theory/Signatures/Signature.lean).

<a id="def-refinement"></a>**Definition 4 (refinement).** For a partition
function $P$ and a BDD $\sigma(\vs, \vec y)$, a partition function $P'$ is a
*refinement of $P$ by $\sigma$* if for all $s, t \in R$:
$\pi_{P'}(s) = \pi_{P'}(t)$ if and only if $\pi_P(s) = \pi_P(t)$ and
$\sigma|_s = \sigma|_t$.

## Algorithm

A refinement is computed by one simultaneous traversal of $\sigma$ and $P$
over the state levels. When both reach the boundary, the pair of boundary
nodes $(\sigma|_s, P|_s)$ identifies the new block of $s$ (Definition 2), and
a memo table maps each pair to one block number. The first pair met for an
old block keeps the old number; each further pair with the same old block
receives a fresh number from a counter $k$ that starts at $|P|$.
Unchanged blocks therefore keep their BDD nodes.

```math algorithm
\begin{algorithmic}[1]
\Function{Refine}{$\sigma, P$}
  \If{$P = 0$} \Return $0$ \Comment{unreachable states}
  \EndIf
  \If{$(\sigma, P) \in \mathrm{dom}(\mathit{memo})$} \Return $\mathit{memo}(\sigma, P)$
  \EndIf
  \If{the top variable $v$ of $\sigma$ and $P$ is a state variable}
    \State $r \gets \mathrm{node}\big(v,\ \Call{Refine}{\sigma|_{v=1}, P|_{v=1}},\ \Call{Refine}{\sigma|_{v=0}, P|_{v=0}}\big)$
  \Else
    \Statex \Comment{boundary: $P$ is the cube $\vb = \beta$, $\sigma$ the signature of the states reaching it}
    \If{$\beta \notin \mathit{claimed}$}
      \State $\mathit{claimed} \gets \mathit{claimed} \cup \{\beta\}$; $r \gets P$
    \Else
      \State $r \gets (\vb = k)$; $k \gets k + 1$
    \EndIf
  \EndIf
  \State $\mathit{memo}(\sigma, P) \gets r$
  \State \Return $r$
\EndFunction
\end{algorithmic}
```

The outer loop starts from $P_0 = R \wedge (\vb = 0)$ and computes
$P_{i+1} = \Refine(\sigma_{P_i}, P_i)$, with $\mathit{memo}$ and
$\mathit{claimed}$ emptied in every iteration and $k$ kept. It stops when
$|P_{i+1}| = |P_i|$ and returns $P_{i+1}$.

## Theorems

<a id="thm-stable-bisimulation"></a>**Theorem 1 (stable partitions are
bisimulations).** If $P$ is stable, then $\pi_P(s) = \pi_P(t)$ implies
$s \leftrightarrow t$. Conversely, bisimilar states are related by the
signature fixed point. Proved in Lean as
[`IsStable.bisimilarity`](https://github.com/MERCorg/merc-verified/blob/main/Challenges/Signatures.lean)
and
[`strongFixPoint`](https://github.com/MERCorg/merc-verified/blob/main/Challenges/Signatures.lean),
for explicit partitions given as functions from states to blocks.

<a id="thm-sigref-correct"></a>**Theorem 2 (termination and result).** The
outer loop stops after at most $|R|$ iterations and returns a partition
function $P$ with $\pi_P(s) = \pi_P(t)$ if and only if $s \leftrightarrow t$,
for all $s, t \in R$. Proved on paper below; the loop itself is not
formalised in Lean.

*Proof idea.* By Definition 4 each $P_{i+1}$ refines $P_i$, so $|P_i|$ never
decreases and is at most $|R|$. If $|P_{i+1}| = |P_i|$, the two partitions
have the same blocks, so states with one block number have the same
signature and $P_{i+1}$ is stable; Theorem 1 gives one direction. For the
other, bisimilar states in one block of $P_i$ have equal signatures, so they
stay in one block of $P_{i+1}$; by induction they share a block of every
$P_i$.

## Implementation

| definition | realised by |
|---|---|
| partition function (Definition 1) | the BDD returned by [`sigref_symbolic`](https://mercorg.github.io/merc/merc_symbolic/fn.sigref_symbolic.html), over the next-state and block variables |
| quotient by a partition function | [`quotient_symbolic`](https://mercorg.github.io/merc/merc_symbolic/fn.quotient_symbolic.html) |

The design decisions are the following.

- **The partition is stored over $\vs'$.** The signature of every iteration
  is then one relational product of $T$ with $P$, and the result is renamed
  from $\vs$ to $\vs'$ once to become the next partition. Storing it over
  $\vs$ would rename $P$ before every product instead.
- **The block width is fixed.** The $m = \lceil \log_2 |R| \rceil$ block
  variables (at least one) are allocated once, below all existing variables.
  Block numbers never exceed $|R|$, so no iteration needs a new variable.
- **The signature can be split by transition group.** With
  `--split-signature`, each iteration uses the signature of one class of
  transition groups, where groups sharing an action label are in one class.
  The fixed point is then reached after a full sweep over the classes in
  which no block was split.
- **Relations can be extended or merged.** With `--extend-relation`, each
  group's relation is extended with $s_j = s'_j$ for the variables it does
  not write. `--merge-transitions` combines the extended relations into one
  relation and implies `--extend-relation`.
- **The constructions do not depend on the variable order.** The boundary
  traversal of Algorithm 1 identifies the state levels through the
  manager's map from variables to levels. The extension with $s_j = s'_j$
  and the quotient are built with BDD operations and a general
  substitution. They are therefore valid under any order that places the
  state variables above the block variables.
  [Stability-based refinement](stability-refinement.md#implementation)
  reorders the manager, and constructions that read a variable number as a
  level gave wrong quotients after the reorder.
- **The boundary traversal is shared.** Stability-based refinement
  renumbers its blocks with Algorithm 1, applied to the signature of a
  single action.

The unit tests compare the quotient with the explicit strong-bisimulation
reduction on random LTSs, and check that `--split-signature` yields the same
number of blocks.

## References

| | reference |
|---|---|
| [vDvdP16] | T. van Dijk and J. van de Pol. *Multi-core Symbolic Bisimulation Minimisation.* TACAS 2016, LNCS 9636, pages 332–348. [DOI](https://doi.org/10.1007/978-3-662-49674-9_19). |
