```math_preamble
\usepackage[paperwidth=60cm,paperheight=60cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{tikz}
% Default \Comment right-justifies with \hfill; keep comments inline (README.md).
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
\newcommand{\vs}{\vec s}
\newcommand{\vx}{\vec x}
\newcommand{\vb}{\vec b}
\newcommand{\B}{\mathbb B}
\newcommand{\Stab}{\mathit{Stab}}
\newcommand{\Split}{\mathit{Split}}
\newcommand{\Refine}{\textsc{Refine}}
```
# Stability-based symbolic refinement

[GL] computes strong bisimilarity on a symbolic LTS by checking, per action
$a$, whether the current partition is stable with one quantified BDD formula,
and by splitting it on an unstable action. The block encoding of [GL] lets a
state belong to a set of block vectors, and two states with overlapping sets
count as one block. This page shows that the algorithm with that encoding
does not terminate on a three-state LTS (Theorem 2). It then gives two
repairs: one renumbers the blocks after every split, the other adds one bit
per split and does not renumber. merc implements both in
[`merc_symbolic`](https://mercorg.github.io/merc/merc_symbolic/index.html):
the renumbering repair as
[`refine_bisimulation`](https://mercorg.github.io/merc/merc_symbolic/fn.refine_bisimulation.html),
run as `merc-sym reduce strong-bisim`, and the splitter bits as
`refine_bisimulation_incremental`, run as
`merc-sym reduce strong-bisim-incremental`. This page assumes
[Signature refinement, Definitions 1 to 4](signature-refinement.md#def-partition-function)
and the notation introduced there.

## Definitions

<a id="def-block-relation"></a>**Definition 1 (block relation).** A *block
relation* is a BDD $B(\vs, \vx)$ over the state variables and a vector
$\vx$ of $\ell$ block variables, with $B(s, x)$ false for $s \notin R$. The
*class set* of $s$ is $S_B(s) = \{x \mid B(s, x)\}$. A partition function is
a block relation in which every class set of a reachable state is a
singleton.

By [Signature refinement, Def. 2](signature-refinement.md#def-boundary-node),
two states have equal class sets if and only if they have the same boundary
node in $B$.

<a id="def-stability"></a>**Definition 2 (overlap stability).** For an
action $a$, $B$ is *stable for $a$* if $\Stab_a(B)$ holds:

```math
$$
\Stab_a(B) = \forall \vs, \vec t, \vs'.\ \big(\exists \vx.\ B(\vs, \vx) \wedge B(\vec t, \vx) \wedge T_a(\vs, \vs')\big) \Rightarrow \exists \vec t', \vx'.\ T_a(\vec t, \vec t') \wedge B(\vs', \vx') \wedge B(\vec t', \vx')
$$
```

The premise relates $s$ and $t$ when $S_B(s) \cap S_B(t) \neq \emptyset$, and
the consequent accepts $t'$ when $S_B(s') \cap S_B(t') \neq \emptyset$.

<a id="def-split"></a>**Definition 3 (split).** The *split* of $B$ on $a$
is the block relation over $1 + 2\ell$ block variables

```math
$$
\Split_a(B)(\vs, y\,\vx_1\,\vx_2) = B(\vs, \vx_1) \wedge \big(y \Leftrightarrow \exists \vs'.\ T_a(\vs, \vs') \wedge B(\vs', \vx_2)\big).
$$
```

## Algorithm

The algorithm of [GL] starts from $B_0 = R$ with $\ell_0 = 0$, and while some
action $a$ has $\neg \Stab_a(B_i)$ it sets $B_{i+1} = \Split_a(B_i)$. When
all actions are stable it returns $B_i$. The block width satisfies
$\ell_{i+1} = 1 + 2\ell_i$, so $\ell_i = 2^i - 1$.

In $\Split_a(B)$ the vector $\vx_2$ is unconstrained. For every
$u \in S_B(s)$ and every $v \in \B^{\ell}$, exactly one value of $y$ is
allowed, so

```math
$$
S_{\Split_a(B)}(s) = \{(h_s(v), u, v) \mid u \in S_B(s),\ v \in \B^\ell\}, \qquad h_s(v) = \exists s'.\ T_a(s, s') \wedge B(s', v).
$$
```

By induction, every class set of $B_i$ has $2^{\ell_i - i}$ elements. This
is one for $B_0$ and $B_1$ and more than one from $B_2$ on, where the class
sets of inequivalent states can overlap.

**Example 1.** Figure 1 shows an LTS with $R = \{s_1, s_2, s_3\}$. The states
$s_1$ and $s_2$ are not bisimilar, because $s_2$ has a $c$-move and $s_1$
has none.

```math
\begin{tikzpicture}[
  >=stealth, thick,
  st/.style={draw, circle, minimum size=0.9cm, font=\small},
  lbl/.style={font=\small}
]
\node[st] (s1) at (0,0) {$s_1$};
\node[st] (s2) at (3,0) {$s_2$};
\node[st] (s3) at (1.5,-2.2) {$s_3$};
\draw[->] (s1) -- node[lbl, left] {$a$} (s3);
\draw[->] (s2) to[bend right=12] node[lbl, left] {$a$} (s3);
\draw[->] (s2) to[bend left=28] node[lbl, right] {$c$} (s3);
\end{tikzpicture}
```

$B_0$ is unstable for $a$, since $s_1 \xrightarrow{a} s_3$ and $s_3$ has no
$a$-move. Splitting on $a$ gives $S_{B_1}(s_1) = S_{B_1}(s_2) = \{1\}$ and
$S_{B_1}(s_3) = \{0\}$. $B_1$ is stable for $a$ and unstable for $c$.
Splitting on $c$ gives, with vectors written $y\,x_1\,x_2$:

| state | $h_s(0)$ | $h_s(1)$ | $S_{B_2}(s)$ |
|---|---|---|---|
| $s_1$ | $0$ | $0$ | $\{010, 011\}$ |
| $s_2$ | $1$ | $0$ | $\{110, 011\}$ |
| $s_3$ | $0$ | $0$ | $\{000, 001\}$ |

The class sets of $s_1$ and $s_2$ share $011$, which reads "no $c$-move into
a state with an $a$-move". It holds for $s_1$ because $s_1$ has no $c$-move
and for $s_2$ because its $c$-move leads to $s_3$. The premise of
$\Stab_c(B_2)$ therefore relates $s_2$ to $s_1$, and $s_1$ cannot match
$s_2 \xrightarrow{c} s_3$.

## Theorems

<a id="thm-stability-partition"></a>**Theorem 1 (stability of partition
functions).** If $B$ is a partition function, then $\Stab_a(B)$ holds for
every action $a$ if and only if $B$ is stable in the sense of
[Signature refinement, Def. 3](signature-refinement.md#def-signature).
Proved on paper; this is the stability condition of [KS90]. Not formalised
in Lean.

*Proof idea.* For singleton class sets, overlap is equality of block
numbers. $\Stab_a(B)$ then states that every $a$-move of $s$ into block
$\beta$ is matched by an $a$-move of $t$ into $\beta$ whenever $s$ and $t$
share a block. This is $\mathit{sig}_B(s) \subseteq \mathit{sig}_B(t)$, and
by symmetry equality.

<a id="thm-nontermination"></a>**Theorem 2 (non-termination).** On the LTS
of Example 1, the algorithm of [GL] does not terminate, whichever unstable
action it splits on. Proved on paper below; not formalised in Lean.

*Proof idea.* Let $U_i = \bigcup_{s \in R} S_{B_i}(s)$. Since $|R| = 3$ and
each class set has $2^{\ell_i - i}$ elements, $|U_i| < 2^{\ell_i}$ for
$i \geq 2$, so some $v \in \B^{\ell_i}$ lies in no class set. For that $v$,
$h_s(v) = 0$ for every $s$ and every split action. Hence, if
$u \in S_{B_i}(x) \cap S_{B_i}(y)$, then $(0, u, v)$ lies in both
$S_{B_{i+1}}(x)$ and $S_{B_{i+1}}(y)$: an overlap at $i \geq 2$ persists in
all later iterations. The first two splits are on $a$ and $c$ in either
order. After $a$ then $c$, the class sets of $s_1$ and $s_2$ overlap (Example 1),
and $\Stab_c$ fails because $s_1$ has no $c$-move. After $c$ then $a$, the class sets of $s_1$
and $s_3$ overlap in $001$, and $\Stab_a$ fails because $s_3$ has no
$a$-move. In both cases the failing action stays unstable in every later
iteration.

Testing equality of class sets instead of overlap does not repair the
algorithm. The class set of $s$ after a split determines only the union of
the class sets of its $a$-successors, and once class sets overlap, that
union need not determine the set of successor classes.

## Repairs

Both repairs keep $B$ a partition function, so that Theorem 1 applies
in every iteration.

**Renumbering.** The boundary node of $s$ in $\Split_a(B)$ is determined by
the pair $(\pi_B(s), \sigma_a|_s)$, where
$\sigma_a(\vs, \vb') = \exists \vs'.\ T_a(\vs, \vs') \wedge B(\vs', \vb')$.
Numbering the boundary nodes of $\Split_a(B)$ is therefore
$\Refine(\sigma_a, B)$ of
[Signature refinement, Def. 4](signature-refinement.md#def-refinement),
restricted to one action. [GL] proposes this renumbering to shorten the block
vectors. By Theorem 2 it is required for correctness. The block
width is then fixed at $m = \lceil \log_2 |R| \rceil$. By Theorem 1,
$\neg \Stab_a(B)$ holds if and only if $|\Refine(\sigma_a, B)| > |B|$, so the
stability check can be replaced by a comparison of block counts, which needs
no copies $\vec t, \vec t'$ of the state variables.

**Splitter bits.** Algorithm 1 avoids renumbering. It takes a violation of
$\Stab_a$, splits on the block $\gamma$ of the successor $s'$ that $t$
cannot match, and appends one bit. Fixing the splitter $\gamma$, in place of the
unconstrained $\vx_2$ of Definition 3, keeps every class set a singleton.
The violations of $\Stab_a$ form the BDD

```math
$$
V_a(\vs, \vec t, \vs') = E(\vs, \vec t) \wedge T_a(\vs, \vs') \wedge \neg \exists \vec t'.\ T_a(\vec t, \vec t') \wedge E(\vs', \vec t'), \qquad E(\vs, \vec t) = \exists \vx.\ B(\vs, \vx) \wedge B(\vec t, \vx),
$$
```

which the stability check computes anyway; one satisfying assignment is the
witness.

```math algorithm
\begin{algorithmic}[1]
\Function{SplitterRefine}{$R, T$}
  \State $B \gets R$; $\ell \gets 0$
  \Loop
    \If{$V_a = \emptyset$ for every action $a$} \Return $B$
    \EndIf
    \State pick $a$ and $(s, t, s') \in V_a$
    \State $\gamma \gets \pi_B(s')$
    \State $B(\vs, \vx\,y) \gets B(\vs, \vx) \wedge \big(y \Leftrightarrow \exists \vs'.\ T_a(\vs, \vs') \wedge B(\vs', \gamma)\big)$; $\ell \gets \ell + 1$
    \Statex \Comment{$y$ is $1$ for $s$ and $0$ for $t$}
  \EndLoop
\EndFunction
\end{algorithmic}
```

<a id="thm-repairs"></a>**Theorem 3 (correctness of the repairs).** Both
repairs terminate after at most $|R| - 1$ splits and return a partition
function $B$ with $\pi_B(s) = \pi_B(t)$ if and only if $s \leftrightarrow t$,
for all $s, t \in R$. Algorithm 1 ends with $\ell \leq |B| - 1$ block
variables. Proved on paper below; not formalised in Lean.

*Proof idea.* Each split separates two states of one block, so $|B|$
increases with every split and is at most $|R|$. At termination every action
is stable and Theorem 1 with
[Signature refinement, Thm. 1](signature-refinement.md#thm-stable-bisimulation)
gives that blocks contain only bisimilar states. Every block is a union of
bisimilarity classes initially, and a split preserves this because bisimilar
states reach the same blocks by $a$.

Algorithm 1 has three costs. Its block width grows linearly with the number of
splits, where renumbering keeps it logarithmic in the number of blocks. Each
iteration splits on one splitter, where renumbering splits on every block
reachable by $a$. A split on $j$ splitters at once appends $j$ bits. Renumbering
can also be applied lazily, when $\ell$ exceeds a constant multiple of
$\lceil \log_2 |B| \rceil$. $|B|$ is the number of distinct boundary nodes
and is counted by one traversal.

## Implementation

[`refine_bisimulation`](https://mercorg.github.io/merc/merc_symbolic/fn.refine_bisimulation.html)
implements the renumbering repair. It checks $\Stab_a$ for each action in
turn, as the emptiness of $V_a$, and splits with the boundary traversal of
[signature refinement](signature-refinement.md#algorithm) applied to
$\sigma_a$. It stops after a pass over all actions without a split. It
returns an error if a split fails to increase the number of blocks, which
Theorem 3 excludes.

`refine_bisimulation_incremental` implements Algorithm 1, run as
`merc-sym reduce strong-bisim-incremental`. It deviates from Algorithm 1 in
two ways.

- **Several splitters per check.** Every block of a target $s'$ of $V_a$ is
  a splitter, so after one stability check the implementation appends one
  bit for each of up to eight such blocks. Each block $\gamma$ is chosen
  from the set of these blocks by fixing the block variables one at a time,
  which does not depend on the variable order. A split on one splitter is
  followed by a full stability check over four copies of the state
  variables, which costs more than the relational product for an extra
  splitter.
- **Lazy renumbering.** After each split the implementation counts the
  boundary nodes. It renumbers the blocks to $\lceil \log_2 |B| \rceil$
  bits when $\ell$ exceeds `--compaction-factor` times that number (2 by
  default), and once at the end. A factor of 0 renumbers only at the end.
  Renumbering assigns $0, 1, \dots$ to the boundary nodes in the order of a
  traversal of $B$ over the state levels. It reuses the lowest block
  variables, and further bits are allocated at the bottom of the variable
  order.

Both variants return an error when the number of blocks does not increase
after a split. The design decisions they share are the following.

- **One relation per action.** $T_a$ is the union over all transition groups
  of the group relation, extended with $s_j = s'_j$ for the variables the
  group does not write, with the action fixed to $a$ and the action variables
  quantified. A bisimulation can match an $a$-move of one group with an
  $a$-move of another, so splitting per group refines too much.
- **Variable order.** $\Stab_a$ uses four copies of the state variables,
  $\vs, \vs', \vec t, \vec t'$. The order is $\vs, \vs'$ interleaved per
  bit, then $\vec t, \vec t'$ interleaved per bit, then the block
  variables. Interleaving all four copies makes
  $E(\vs, \vec t) = R(\vs) \wedge R(\vec t)$ for $B_0$ a product of two
  independent sets, whose BDD can be quadratic in that of $R$. With $\vs$
  above $\vec t$, the BDD of $E$ grows with the number of blocks. The
  renaming from $\vs$ to $\vs'$ moves every variable to the adjacent level;
  the copies $\vec t, \vec t'$ are introduced by a general substitution.
- **Fixed block width.** As in signature refinement, the
  $\lceil \log_2 |R| \rceil$ block variables and their primed copies are
  allocated once, with each copy directly below its variable. $|R|$ is
  counted over all variables of the manager and divided by the number of
  assignments to the other variables, which is valid in any variable order.
  When the count is approximate, one extra block variable is allocated.
- **Output.** The result is a partition function over the next-state and
  block variables, as for
  [`sigref_symbolic`](https://mercorg.github.io/merc/merc_symbolic/fn.sigref_symbolic.html),
  so both are passed to the same quotient construction. The unit tests
  compare the quotient with the explicit strong-bisimulation reduction on
  random LTSs.

## References

| | reference |
|---|---|
| [GL] | J. F. Groote and M. Laveaux. *Determining bisimulation using BDDs.* Unpublished manuscript. |
| [KS90] | P. C. Kanellakis and S. A. Smolka. *CCS Expressions, Finite State Processes, and Three Problems of Equivalence.* Information and Computation 86(1), pages 43–68, 1990. [DOI](https://doi.org/10.1016/0890-5401(90)90025-D). |
