```math_preamble
\newcommand{\PBES}{\mathcal{E}}
```
# Parameterised Boolean equation systems

A *parameterised Boolean equation system* (PBES) is a sequence of fixpoint
equations over predicates with data parameters. PBESs are the target of model
checking modal $\mu$-calculus formulas with data: solving the PBES answers the
model checking question. This page defines PBESs and the classes of formulas and
PBESs that the other pages of the PBES section rely on (Definitions 1 to 4). merc stores PBESs in the
[`merc_pbes`](https://mercorg.github.io/merc/merc_pbes/) crate, in the same
term format as mCRL2, so that `.pbes` files can be read and written as is.

## Syntax

<a id="def-pbes"></a>**Definition 1 (PBES).** A *predicate formula* $\varphi$ is built from Boolean data expressions $b$,
propositional variable instantiations $X(e)$, the connectives and quantifiers
over data variables $d$ of sort $D$:

```math
\[
\varphi ::= b \mid X(e) \mid \neg\varphi \mid \varphi \land \varphi \mid
\varphi \lor \varphi \mid \varphi \Rightarrow \varphi \mid
\forall d{:}D \ldotp \varphi \mid \exists d{:}D \ldotp \varphi
\]
```

where $e$ is a sequence of data expressions. A PBES is a sequence of
equations, each defining one propositional variable:

```math
\[
\PBES ::= \emptyset \mid (\mu X(d{:}D) = \varphi)\,\PBES \mid (\nu X(d{:}D) = \varphi)\,\PBES
\]
```

where $\mu$ and $\nu$ are the least and greatest fixpoint operators, $X$ is a
propositional variable of sort $D \rightarrow \mathbb{B}$, $d = (d_1, \ldots,
d_m)$ are its parameters, and the right-hand side $\varphi$ is syntactically
monotone, i.e. no propositional variable occurs under an odd number of
negations. The order of the equations matters: earlier equations take priority
over later ones. A PBES comes with an initial state $X(e)$, the instantiation
whose truth value is of interest, and may declare *global variables*, which can
occur free in every equation and stand for arbitrary values.

In merc, `Pbes`
stores the data specification, the global variables, the equations and the
initial state. The right-hand sides are
`PbesExpression`s,
maximally shared terms, so that equality and hashing take constant time and the
long chains that, for example, quantifier enumeration produces are cheap to
copy. Use `PbesExpressionRef::kind` to match on the top-level shape of an
expression. The Boolean constants are the data literals `true` and `false`,
exactly as in mCRL2.

## Simple formulas {#simple-formulas}

<a id="def-simple-formula"></a>**Definition 2 (simple formula).** A predicate formula is *simple* if it contains
no propositional variable instantiations, so that its truth value is determined by its data alone. Simple
formulas play the role of conditions in the
[standard recursive form](srf_transformation.md).

A PBES generated for evidence contains *counter-example* propositional
variables, `Zpos` and `Zneg`, whose equations are $\mathit{true}$ and
$\mathit{false}$. A formula whose only instantiations are of these variables is
*pseudo-simple*, see the [counter-example encoding](counter_examples.md).

## Normalisation

<a id="def-normalised-pbes"></a>**Definition 3 (normalised PBES).** A PBES is *normalised* if negations and
implications occur only inside data expressions, i.e. the right-hand sides only use $\land$, $\lor$, $\forall$,
$\exists$ on top of data expressions and instantiations. Any PBES can be
normalised by pushing negations inwards, using the De Morgan laws and the
dualities between the quantifiers and the fixpoint operators. The
[SRF transformation](srf_transformation.md) assumes its input is normalised.

## Well-typedness {#well-typedness}

<a id="def-well-typed-pbes"></a>**Definition 4 (well-typed PBES).** A PBES is *well-typed* if

- the names of the equations, of the parameters of each equation, and of the
  global variables are unique;
- a quantifier variable has a different name than the parameters of its
  equation and than the variables of the quantifiers it occurs in, and it is not
  a global variable;
- every free variable is a global variable;
- every instantiation, including the initial state, refers to a declared
  propositional variable, with as many arguments as it has parameters and of
  the same sorts.

`Pbes::check_well_typed`
checks Definition 4. Sorts are compared as terms, so they must be normalised, whereas mCRL2 compares
them modulo sort aliases. Unlike mCRL2, merc also rejects an instantiation of an
undeclared propositional variable.

The second condition, that no quantifier *shadows* another variable, is not
only a matter of hygiene. Transformations such as the
[SRF transformation](srf_transformation.md#variable-capture) move conditions
from outside a quantifier to underneath it, which silently changes their meaning
when the quantifier binds a variable of the same name. The parser of mCRL2
renames such variables, but its PBES library does not check for them, so a PBES
that is constructed or read in another way can still violate this condition.
