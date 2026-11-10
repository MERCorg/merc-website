```math_preamble
\newcommand{\PRES}{\mathcal{E}}
\newcommand{\R}{\overline{\mathbb{R}}}
```
# Parameterised real equation systems

A *parameterised real equation system* (PRES) is the quantitative counterpart of
a [PBES](pbes.md): its equations define functions from data to the extended
reals $\R = \mathbb{R} \cup \{-\infty, +\infty\}$ instead of to the Booleans.
PRESs are the target of model checking *quantitative* modal formulas, for
example the probability that a property holds or the expected reward, on
probabilistic processes, just like PBESs are for ordinary modal formulas.
mCRL2 implements them in its `pres` library, with `lps2pres` translating a
linear stochastic process and a formula to a PRES, and `pressolve` solving it.
merc does not implement PRESs.

## Syntax

This page defines PRESs (Definition 1), as mCRL2 implements them, for comparison
with [PBESs](pbes.md).

<a id="def-pres"></a>**Definition 1 (PRES).** A *PRES expression* $\varphi$ is built from real-valued data expressions $r$,
propositional variable instantiations $X(e)$, and the following operators, where
$c$ is a positive constant and $d$ a data variable of sort $D$:

```math
\[
\begin{aligned}
\varphi ::= {} & r \mid X(e) \mid -\varphi \mid \varphi \land \varphi \mid
\varphi \lor \varphi \mid \varphi \Rightarrow \varphi \mid \varphi + \varphi \mid
c \cdot \varphi \mid \varphi \cdot c \\
\mid {} & \inf_{d{:}D} \varphi \mid \sup_{d{:}D} \varphi \mid \sum_{d{:}D} \varphi
\end{aligned}
\]
```

A PRES is a sequence of equations with an initial state, exactly like a PBES:

```math
\[
\PRES ::= \emptyset \mid (\mu X(d{:}D) = \varphi)\,\PRES \mid (\nu X(d{:}D) = \varphi)\,\PRES
\]
```

where $X$ is now a propositional variable of sort $D \rightarrow \R$.

## Semantics

Given values for the propositional variables, an expression denotes an extended
real:

- the Booleans are embedded as $\mathit{true} = +\infty$ and $\mathit{false} = -\infty$;
- $-\varphi$ negates, and $\varphi \land \psi$ and $\varphi \lor \psi$ are the
  minimum and the maximum of their operands;
- $\varphi \Rightarrow \psi$ abbreviates $-\varphi \lor \psi$;
- $\varphi + \psi$ is addition, and $c \cdot \varphi$ and $\varphi \cdot c$
  multiply by the positive constant $c$, which keeps them monotone;
- $\inf_{d{:}D} \varphi$ and $\sup_{d{:}D} \varphi$ are the infimum and the
  supremum over all values of $d$, generalising $\forall$ and $\exists$, and
  $\sum_{d{:}D} \varphi$ is the sum over all values of $d$, which is how
  probabilistic choices are encoded.

Every operator except $-$ is monotone, so as for PBESs the right-hand sides must
be *syntactically monotone*: no propositional variable may occur under an odd
number of negations, counting the left-hand side of $\Rightarrow$. The extended
reals with their usual order form a complete lattice, so every equation has a
least ($\mu$) and a greatest ($\nu$) solution, and the solution of a PRES is
defined from the last equation to the first exactly as for PBESs, with earlier
equations taking priority.

Restricting the data expressions to $\mathit{true}$ and $\mathit{false}$ and the
operators to $\land$, $\lor$, $\inf$ and $\sup$ gives back a PBES, with $\inf$
and $\sup$ as $\forall$ and $\exists$.

## Normalisation and auxiliary operators

As for PBESs, a PRES is normalised by pushing the negations inwards: $-$
swaps $\land$ and $\lor$, and $\inf$ and $\sup$, $\Rightarrow$ becomes $\lor$
with a negated left-hand side, and a negation that reaches a data expression is
absorbed into it.

The solution algorithms of mCRL2, such as its Gauss elimination for real
equation systems, produce four more operators, which therefore also occur in its
term format: $\mathit{eqinf}(\varphi)$ and $\mathit{eqninf}(\varphi)$, which
indicate whether $\varphi$ is $+\infty$ respectively $-\infty$, and two
conditionals, written $(\varphi_1 \rightarrow \varphi_2 \diamond \varphi_3)$ and
$(\varphi_1 \Rightarrow \varphi_2 \diamond \varphi_3)$, whose condition
$\varphi_1$ is compared with $0$, strictly ($< 0$) respectively non-strictly
($\leq 0$). They do not occur in a PRES generated from a formula.
