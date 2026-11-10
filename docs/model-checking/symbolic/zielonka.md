```math_preamble
\usepackage[paperwidth=60cm,paperheight=60cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
% Default \Comment right-justifies with \hfill.
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
\newcommand{\G}{\mathcal G}
\newcommand{\Attr}{\mathrm{Attr}}
\newcommand{\SAttr}{\mathrm{SAttr}}
```
# Zielonka's algorithm

The symbolic solver of [`merc_vpg`](https://mercorg.github.io/merc/merc_vpg/index.html)
is Zielonka's recursive algorithm over LDDs. This page defines the attractor
(Definition 1), gives the algorithm, and states its correctness (Theorems 1 and 2),
which is proved in Lean. See [Partial solving](partial-solving.md) for how the
same attractor computation is run *during* exploration, before the graph is fully
known, to decide vertices on the fly.

## Priority direction: max-parity vs min-parity

merc's priorities are a **max-parity** encoding: the outermost fixpoint block gets the *largest*
priority, a priority `p` belongs to Even exactly when `p` is even, and the solver picks the highest
priority present. mCRL2's symbolic solver is **min-parity**: the outermost block gets rank 0, and
it picks the smallest rank instead, with `alpha = m % 2`.

## Attractors

<a id="def-attractor"></a>**Definition 1 (attractor).** For a parity game $\G = (V, V_0, V_1, E,
\mathrm{priority})$ with players $\alpha$ and $\bar\alpha$, the *control
predecessor* of $U \subseteq V$ is

```math
$$
\mathrm{cpre}_\alpha(\G, U) = \{v \in V_\alpha \mid \exists (v, w) \in E.\ w \in U\} \cup \{v \in V_{\bar\alpha} \mid \forall (v, w) \in E.\ w \in U\}
$$
```

and the *attractor* $\Attr_\alpha(\G, U)$ is the least fixed point
$\mu Z.\ U \cup \mathrm{cpre}_\alpha(\G, Z)$: the vertices from which
$\alpha$ can force play into $U$.

<a id="thm-attractor"></a>**Theorem 1 (attractor).** $U \subseteq \Attr_\alpha(\G, U)$, the complement
$V \setminus \Attr_\alpha(\G, U)$ is again a (total) subgame, no vertex of
$\alpha$ in the complement has an edge into the attractor, and $\alpha$ has a
positional strategy that forces every play from the attractor into $U$.

## The recursive algorithm

For a parity game $\G = (V, V_0, V_1, E, \mathrm{priority})$, Zielonka's algorithm peels off, in
each recursive call, the attractor of the highest priority present, recurses on what remains, and
then decides — depending on whether the opponent won anything at all in the remainder — whether one
more attractor and one more recursive call are needed to correctly attribute that remainder:

```math algorithm
\begin{algorithmic}[1]
\Function{Zielonka}{$\G$}
  \If{$V = \emptyset$}
    \State \Return $(\emptyset, \emptyset)$
  \EndIf
  \State $d \gets \max\{\mathrm{priority}(v) \mid v \in V\}$ \Comment{highest priority present (max-parity, see above)}
  \State $\alpha \gets \Call{PlayerOfPriority}{d}$
  \State $U \gets \{v \in V \mid \mathrm{priority}(v) = d\}$
  \State $A \gets \Attr_\alpha(\G, U)$ \Comment{safety: on-the-fly, $\Attr_\alpha$ here is $\SAttr_\alpha$, folding in the incomplete set --- see partial-solving.md}
  \State $(W_0', W_1') \gets \Call{Zielonka}{\G \setminus A}$
  \If{$W_{\bar\alpha}' = \emptyset$}
    \State $W_\alpha \gets V \setminus W_{\bar\alpha}'$ \Comment{$= A \cup W_\alpha'$, nothing more to attribute to $\bar\alpha$}
    \State $W_{\bar\alpha} \gets \emptyset$
  \Else
    \State $B \gets \Attr_{\bar\alpha}(\G, W_{\bar\alpha}')$ \Comment{safety: same substitution as above}
    \State $(W_0'', W_1'') \gets \Call{Zielonka}{\G \setminus B}$
    \State $W_\alpha \gets W_\alpha''$
    \State $W_{\bar\alpha} \gets W_{\bar\alpha}'' \cup B$
  \EndIf
  \State \Return $(W_0, W_1)$
\EndFunction
\end{algorithmic}
```

The two marked lines are the only places the recursion ever asks "who controls reaching this set" —
everywhere else it only removes vertices and recurses. That is also why on-the-fly partial solving
(next page) needs to touch nothing but those two computations: substituting the safe attractor
$\SAttr_\alpha$ for $\Attr_\alpha$ there is enough to keep the whole recursion sound against a graph
that is still being explored.

<a id="thm-correctness-of-zielonka-s-algorithm"></a>**Theorem 2 (correctness of Zielonka's algorithm).** For every finite parity
game, the winning regions that Zielonka's algorithm returns partition the
vertices, and each player's positional strategy wins from every vertex of that
player's region. In particular, parity games are positionally determined.

Theorems 1 and 2 are proved in Lean, without `sorry`, in the
[`MercLib/ParityGame`](https://github.com/MERCorg/merc-verified/tree/main/MercLib/ParityGame) library of merc-verified:

| theorem | Lean |
|---|---|
| Theorem 1 | `Game.attractorCorrect`, for `Game.attr` |
| Theorem 2 | `Game.ZielonkaCorrect`, stated with `Solves` |

The Lean formalisation is of the explicit algorithm on sets; the symbolic
implementation over LDDs is not verified against it.

## Strategy representation

A strategy is an LDD over the doubled, interleaved state vector `[from₀, to₀, from₁, to₁, …]` —
the same layout the edge relations use. Applying a strategy projects it onto
`2*read_idx`/`2*write_idx+1` and intersects it with each group's relation, which is why the layout
is not free to choose: any other layout would need a translation step in the innermost loop of the
only consumer. A dedicated merge operation builds this interleaved cartesian product.
