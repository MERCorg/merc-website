```math_preamble

\usepackage[paperwidth=40cm,paperheight=25cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
% Default \Comment right-justifies with \hfill, which — combined with a wide
% page to fit long comments — leaves a huge blank gap between code and
% comment, and dvisvgm's tightpage crop then bakes that gap into the SVG:
% CSS stretches the whole (mostly blank) image to the page width, shrinking
% the actual pseudocode. Keep comments inline instead. See README.md.
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
```
# Symmetry quotienting

This page defines the representative function that merc uses to quotient a PBES
by a symmetry group (Definitions 1 and 2), and the algorithm that computes it
(Theorem 1). It assumes the symmetry group found on
the symmetry detection graph ([Symmetry detection graph, Theorem 1](symmetry-detection-graph.md#thm-symmetries-from-automorphisms-blnw)).

`merc_pbes` quotients the state space of a PBES by a symmetry group found on its
symmetry detection graph using a base and strong generating set (BSGS). Following
the paper (*Symmetry Reduction for Parameterised Boolean Equation
Systems*), every PVI that is instantiated is replaced by a *representative*:
`rep` is applied to the initial valuation and to the arguments of every PVI of
an instantiated right-hand side, so symmetric PVIs share one vertex.
The BSGS is used to canonicalize orbits efficiently. Below is an exposition of
the algorithm used.

## Representative function

<a id="def-representative-function"></a>**Definition 1 (representative function).** For a symmetry group $G$ acting on
parameter vectors, a *representative function* is an idempotent function
$\mathit{rep}$ such that $\mathit{rep}(t) = \mathit{rep}(t')$ implies
$\exists \pi \in G.\ \pi(t) = t'$. It is *canonical* if the converse also
holds.

The paper requires a representative function. merc's is moreover canonical: it
is $\mathit{rep}(t) = \min_{\mathrm{lex}} \{\pi(t) \mid \pi \in G\}$, the
lexicographically minimal element of the orbit of the parameter vector. As the paper notes,
this gives maximal reduction of the number of equations, at the price of
computing the full orbit minimum. The BSGS is obtained from GAP's
`ExplicitBSGS`, with a local Schreier–Sims fallback when GAP is unavailable.

## Stabilizer chains

<a id="def-stabilizer-chain"></a>**Definition 2 (stabilizer chain).** A group $G \leq \mathrm{per}([n])$ acting on
the parameter block gives a descending chain of stabilizers $G = G_0 \geq G_1 \geq G_2 \geq \dots$ along a
*base* — a sequence of points $\beta_0, \beta_1, \dots$ — where each $G_i = \{\, \alpha \in G_{i-1} \mid \alpha(\beta_i) = \beta_i \,\}$ is the stabilizer
of $\beta_i$ within the previous group in the chain. The base together with
generators of every $G_i$ is a *base and strong generating set* (BSGS).

Each $G_i$ acts on the previous one's coset space via a *transversal* $U_i$:
a set of representatives, one per orbit point of $\beta_i$ under $G_{i-1}$,
so that every $\alpha \in G_{i-1}$ factors uniquely as $\alpha = u \circ \gamma$
for some $u \in U_i$ and $\gamma \in G_i$. Chaining this over the whole base
gives every $\sigma \in G$ a unique factorisation $\sigma = u_1 \circ \dots
\circ u_k$, $u_i \in U_i$ — the fact both algorithms below exploit: fixing $u_1, \dots, u_i$ already fixes
$\sigma(\beta_j)$ for every $j \leq i$, no matter what the remaining factors
turn out to be. This unique factorisation is standard (see any text on
Schreier–Sims).

## Naive algorithm

The paper uses stabilizer chains without spelling out the loop; the
straightforward reading picks the base $\beta_i = i$ for every position — the
*full* base $0, 1, \dots, n-1$. Every position gets its own level, whether or
not the group actually moves it; a position the group fixes just gets a
singleton transversal $U_i = \{\mathrm{id}\}$. As pseudocode:

```math algorithm
\begin{algorithmic}[1]
\Function{Canonicalize}{}
  \State $\mathit{current} \gets \{\mathrm{id}\}$
  \For{$j \gets 0$ \textbf{to} $n-1$}
    \State $\mathit{best} \gets \infty; \quad \mathit{next} \gets \emptyset$
    \ForAll{$\mathit{prefix} \in \mathit{current}$}
      \ForAll{$u \in U_j$}
        \State $\mathit{value} \gets \mathit{params}[(\mathit{prefix} \circ u)(j)]$
        \If{$\mathit{value} < \mathit{best}$}
          \State $\mathit{best} \gets \mathit{value}; \quad \mathit{next} \gets \{\mathit{prefix} \circ u\}$
        \ElsIf{$\mathit{value} = \mathit{best}$}
          \State $\mathit{next} \gets \mathit{next} \cup \{\mathit{prefix} \circ u\}$
        \EndIf
      \EndFor
    \EndFor
    \State $\mathit{current} \gets \mathit{next}$
  \EndFor
  \State \Return $\mathit{params}$ permuted by any element of $\mathit{current}$
\EndFunction
\end{algorithmic}
```

The load-bearing detail, easy to read past: the inner loop runs — and
`current` gets filtered on `value` — **even when `U[j]` is a singleton**.
A position the group fixes still gets compared, it just never branches. That
turns out to matter more than it looks like it should.

## Compressed base and Schreier–Sims levels

Building a level for every one of the $n$ positions is wasteful when the
group's support is small relative to $n$ — a symmetry that only permutes a
handful of a PBES's data parameters still leaves a base of length $n$ under
that recipe, almost all of it singleton transversals contributing
nothing but bookkeeping. `merc`'s `Bsgs` instead builds a **Schreier–Sims
base**: at each level, $\beta_i$ is chosen as the smallest point some
generator of $G_{i-1}$ actually moves, and the recursion stops once no
generator moves anything. Positions the group fixes at that depth never get a
`SchreierLevel` at all — the chain only holds points that genuinely branch.

This is the actual size reduction: no orbit-transversal BFS, no Schreier
generators, no `HashMap`-backed transversal is ever built for a fixed point.
It is *not* a reduction in how many positions `canonicalize` has to look at —
it still has to visit every index $j$ from $0$ to $n-1$ in order, for exactly
the reason the naive loop does: lexicographic order is decided
position by position, and skipping one silently means silently deciding it's
irrelevant, which is only sometimes true (see below).

<a id="thm-canonicalization"></a>**Theorem 1 (canonicalization).** For a BSGS of $G$ whose base contains every
point that $G$ moves, both algorithms below return
$\min_{\mathrm{lex}} \{\pi(t) \mid \pi \in G\}$.

*Proof idea.* By the unique factorisation, the candidates kept after position $j$
are exactly the products of transversal elements that minimise the first $j+1$
entries of the permuted vector, so after the last position every remaining
candidate yields the orbit minimum. A position outside the base is fixed by the
stabilizer reached so far, and only filters the candidates. Argued on paper; not
formalised in Lean.

## The optimised pseudocode

Canonicalization walks $j = 0, \dots, n-1$ against the compressed chain.
At a real base point it does what the naive loop does. Everywhere else, it
reconstructs that loop's filtering effect by hand, without the singleton
transversal ever being materialized:

```math algorithm
\begin{algorithmic}[1]
\Function{Canonicalize}{$\mathit{chain}$}
  \State $\mathit{current} \gets \{\mathrm{id}\}$
  \State $\mathit{level} \gets \mathit{chain}.\Call{FirstLevel}{}$
  \For{$j \gets 0$ \textbf{to} $n-1$}
    \If{$\mathit{level}$ exists \textbf{and} $\mathit{level}.\mathit{base\_point} = j$}
      \Statex \Comment{a real base point --- search its transversal}
      \State $\mathit{best} \gets \infty; \quad \mathit{next} \gets \emptyset$
      \ForAll{$\mathit{prefix} \in \mathit{current}$}
        \ForAll{$u \in \mathit{level}.\mathit{transversal}$}
          \State $\mathit{value} \gets \mathit{params}[(\mathit{prefix} \circ u)(j)]$
          \If{$\mathit{value} < \mathit{best}$}
            \State $\mathit{best} \gets \mathit{value}; \quad \mathit{next} \gets \{\mathit{prefix} \circ u\}$
          \ElsIf{$\mathit{value} = \mathit{best}$}
            \State $\mathit{next} \gets \mathit{next} \cup \{\mathit{prefix} \circ u\}$
          \EndIf
        \EndFor
      \EndFor
      \State $\mathit{current} \gets \mathit{next}$
      \State $\mathit{level} \gets \mathit{chain}.\Call{LevelAfter}{\mathit{level}}$
    \Else
      \Statex \Comment{$j$ is fixed by the stabilizer reached so far}
      \State $\mathit{best} \gets \infty; \quad \mathit{next} \gets \emptyset$
      \ForAll{$\mathit{prefix} \in \mathit{current}$}
        \State $\mathit{value} \gets \mathit{params}[\mathit{prefix}[j]]$
        \If{$\mathit{value} < \mathit{best}$}
          \State $\mathit{best} \gets \mathit{value}; \quad \mathit{next} \gets \{\mathit{prefix}\}$
        \ElsIf{$\mathit{value} = \mathit{best}$}
          \State $\mathit{next} \gets \mathit{next} \cup \{\mathit{prefix}\}$
        \EndIf
      \EndFor
      \State $\mathit{current} \gets \mathit{next}$
    \EndIf
  \EndFor
  \State \Return $\mathit{params}$ permuted by any element of $\mathit{current}$
\EndFunction
\end{algorithmic}
```

The `else` branch is doing exactly the naive inner loop with `U[j] =
{identity}` substituted in and the now-pointless composition dropped — same
filter, same cost per candidate, just without ever allocating a transversal
to hold the one element that loop would have used.
