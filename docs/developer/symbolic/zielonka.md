```math_preamble
\usepackage[paperwidth=60cm,paperheight=60cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
\newcommand{\G}{\mathcal G}
\newcommand{\Attr}{\mathrm{Attr}}
\newcommand{\SAttr}{\mathrm{SAttr}}
```
# Zielonka's algorithm

See [Partial solving](partial-solving.md) for how the same $\Attr_\alpha$
computation below is run *during* exploration — before the graph is fully
known — to decide vertices on the fly, rather than only after the recursion
here has a complete graph to work with.

## Priority direction: max-parity vs min-parity

merc's `Priority` is a **max-parity** encoding: the outermost fixpoint block gets the *largest*
priority, `Player::from_priority(p) == Even` iff `p` is even, and the explicit `solve_zielonka`
picks the highest priority present. mCRL2's symbolic solver is **min-parity**: the outermost block
gets rank 0, and `get_min_rank` picks the smallest, with `alpha = m % 2`.

## The recursive algorithm

For a parity game $\G = (V, V_0, V_1, E, \mathrm{priority})$, Zielonka's algorithm peels off, in
each recursive call, the attractor of the highest priority present, recurses on what remains, and
then decides — depending on whether the opponent won anything at all in the remainder — whether one
more attractor and one more recursive call are needed to correctly attribute that remainder:

```math
\begin{algorithmic}[1]
\Function{Zielonka}{$\G$}
  \If{$V = \emptyset$}
    \State \Return $(\emptyset, \emptyset)$
  \EndIf
  \State $d \gets \max\{\mathrm{priority}(v) \mid v \in V\}$ \Comment{highest priority present (max-parity, see above)}
  \State $\alpha \gets \textsc{Player::from\_priority}(d)$
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

## Strategy representation

A strategy is an LDD over the doubled, interleaved state vector `[from₀, to₀, from₁, to₁, …]` —
the same layout the edge relations use. `apply_strategy` projects the strategy onto
`2*read_idx`/`2*write_idx+1` and intersects it with each group's relation, which is why the layout
is not free to choose: any other layout would need a translation step in the innermost loop of the
only consumer. `merge` builds this interleaved cartesian product.
