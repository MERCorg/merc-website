```math_preamble
\usepackage[paperwidth=60cm,paperheight=60cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
\newcommand{\PBES}{\mathcal{E}}
\newcommand{\TRUE}{\mathit{true}}
\newcommand{\FALSE}{\mathit{false}}
\newcommand{\Xtrue}{X_{\mathit{true}}}
\newcommand{\Xfalse}{X_{\mathit{false}}}
```
# Standard recursive form

The *standard recursive form* (SRF) is a normal form for
[PBESs](pbes.md) whose structure is similar to that of a linear process
specification: every equation is a disjunction or a conjunction of *summands*,
each of which recurses into a single propositional variable under a simple
condition. This makes the PBES directly explorable as a parity game, where
every summand is a transition group, which is how the explicit and symbolic
PBES solvers use it. The definitions and rules below follow the developer
documentation of the mCRL2 PBES library, which merc's
[`pbes_to_srf`](https://mercorg.github.io/merc/merc_pbes/)
ports.

## Definition

<a id="def-standard-recursive-form"></a>**Definition 1 (standard recursive form).** A PBES $\PBES$ is in SRF iff for every equation $\sigma_i X_i(d{:}D) =
\varphi \in \PBES$ the right-hand side $\varphi$ is either *disjunctive*:

```math
\[
\sigma_i X_i(d{:}D) = \bigvee_{j \in J_i} \exists e_j{:}E_j \ldotp
f_{ij}(d, e_j) \land X_{g_{ij}}(h_{ij}(d, e_j))
\]
```

or *conjunctive*:

```math
\[
\sigma_i X_i(d{:}D) = \bigwedge_{j \in J_i} \forall e_j{:}E_j \ldotp
f_{ij}(d, e_j) \Rightarrow X_{g_{ij}}(h_{ij}(d, e_j))
\]
```

where $d = (d_1, \ldots, d_m)$, every condition $f_{ij}$ is a
[simple formula](pbes.md#simple-formulas), and every summand $j$ contains
exactly one instantiation. A summand is thus a triple $(e_j, f_{ij},
X_{g_{ij}}(h_{ij}(d, e_j)))$ of its quantified variables, its condition and its
target; an empty $e_j$ means that there is no quantifier.
`SrfSummand`
stores exactly these three parts, and
`SrfEquation`
records whether the equation is conjunctive.

A simple subformula that is not a condition has no instantiation to recurse
into. The transformation therefore introduces two *escape equations*, $\mu
\Xfalse = \FALSE \lor \Xfalse$ and $\nu \Xtrue = \Xtrue$, which are $\FALSE$ and
$\TRUE$ respectively. A simple $f$ becomes the summand $f \land \Xtrue$ in a
disjunctive equation, and $\neg f \Rightarrow \Xfalse$ in a conjunctive one.

<a id="def-total-srf"></a>**Definition 2 (total SRF).** An SRF PBES is *total* if, for every parameter valuation, every equation has at
least one summand whose condition holds, so that every vertex of the parity game
has a successor. Adding the summand $\TRUE \Rightarrow \Xtrue$ to every
conjunctive equation and $\TRUE \land \Xfalse$ to every disjunctive one makes it
total without changing the solution, see
`SrfPbes::make_total`.

## Classifying equations

Whether an equation becomes conjunctive or disjunctive is decided from the top
of its (normalised) right-hand side alone:

```math
\[
\mathit{conj}(\varphi) =
\begin{cases}
\FALSE & \text{if } \varphi \text{ is simple, an instantiation } X(e) \text{ or } \exists W \ldotp \varphi' \\
\TRUE & \text{if } \varphi = \forall W \ldotp \varphi' \\
\TRUE \text{ iff one operand is simple and the other an instantiation} & \text{if } \varphi = \varphi_1 \lor \varphi_2 \\
\FALSE \text{ iff one operand is simple and the other an instantiation} & \text{if } \varphi = \varphi_1 \land \varphi_2
\end{cases}
\]
```

The two exceptions for $\lor$ and $\land$ recognise a single summand: $f \land
X(e)$ is the disjunctive summand with condition $f$, and $f \lor X(e)$ is the
conjunctive summand $\neg f \Rightarrow X(e)$.

## Transformation rules

The transformation of the right-hand side $\varphi$ of an equation with fixpoint
symbol $\sigma$ is given by $R_{\lor,\sigma}(\varphi, V)$ for a disjunctive
equation and $R_{\land,\sigma}(\varphi, V)$ for a conjunctive one, where $V$ are
the data variables in scope: the parameters $d$ of the equation and every
quantifier variable bound on the way down. Each yields a pair of the summands
for $\varphi$ and the new equations $\PBES^\varphi$ that had to be introduced
for subformulas that cannot be summands themselves. Such a subformula is
deferred to an equation $\sigma \tilde{X}(V) = \psi$ for a fresh name
$\tilde{X}$, which is transformed in turn, and the summand recurses into
$\tilde{X}(V)$ instead. The rules are applied in order, $f$ ranges over simple
formulas, and $\varphi, \psi$ over formulas that are not simple:

```math
\begin{alignat*}{3}
& R_{\lor,\sigma}(f, V)                       && = &&\; \langle f \land \Xtrue, \emptyset \rangle\\
& R_{\lor,\sigma}(X(e), V)                    && = &&\; \langle \TRUE \land X(e), \emptyset \rangle\\
& R_{\lor,\sigma}(\varphi \land f, V)         && = &&\; \langle \textstyle\bigvee_{i \in I^\varphi} \exists W_i \ldotp f \land f_i \land X_i(g_i), \PBES^\varphi \rangle \\
& ~                                           && ~ &&\; \quad \text{where } \langle \textstyle\bigvee_{i \in I^\varphi} \exists W_i \ldotp f_i \land X_i(g_i), \PBES^\varphi \rangle = R_{\lor,\sigma}(\varphi, V)\\
& R_{\lor,\sigma}(f \land \varphi, V)         && = &&\; R_{\lor,\sigma}(\varphi \land f, V)\\
& R_{\lor,\sigma}(\varphi \land \psi, V)      && = &&\; \langle \TRUE \land \tilde{X}(V), (\sigma\tilde{X}(V) = \varphi \land \psi) \rangle \\
& R_{\lor,\sigma}(\varphi \lor \psi, V)       && = &&\; \langle \textstyle\bigvee_{i \in I^\varphi \cup I^\psi} \exists W_i \ldotp f_i \land X_i(g_i), \PBES^\varphi\PBES^\psi \rangle\\
& R_{\lor,\sigma}(\forall W \ldotp \varphi, V) && = &&\; \langle \TRUE \land \tilde{X}(V), (\sigma\tilde{X}(V) = \forall W \ldotp \varphi) \rangle\\
& R_{\lor,\sigma}(\exists W \ldotp \varphi, V) && = &&\; \langle \textstyle\bigvee_{i \in I^\varphi} \exists W \cup W_i \ldotp f_i \land X_i(g_i), \PBES^\varphi \rangle\\
& ~                                           && ~ &&\; \quad \text{where } \langle \textstyle\bigvee_{i \in I^\varphi} \exists W_i \ldotp f_i \land X_i(g_i), \PBES^\varphi \rangle = R_{\lor,\sigma}(\varphi, V \cup W)
\end{alignat*}
```

and dually for conjunctive equations:

```math
\begin{alignat*}{3}
& R_{\land,\sigma}(f, V)                       && = &&\; \langle \neg f \Rightarrow \Xfalse, \emptyset \rangle\\
& R_{\land,\sigma}(X(e), V)                    && = &&\; \langle \TRUE \Rightarrow X(e), \emptyset \rangle\\
& R_{\land,\sigma}(\varphi \land \psi, V)      && = &&\; \langle \textstyle\bigwedge_{i \in I^\varphi \cup I^\psi} \forall W_i \ldotp f_i \Rightarrow X_i(g_i), \PBES^\varphi\PBES^\psi \rangle\\
& R_{\land,\sigma}(\varphi \lor f, V)          && = &&\; \langle \textstyle\bigwedge_{i \in I^\varphi} \forall W_i \ldotp (\neg f \land f_i) \Rightarrow X_i(g_i), \PBES^\varphi \rangle \\
& ~                                            && ~ &&\; \quad \text{where } \langle \textstyle\bigwedge_{i \in I^\varphi} \forall W_i \ldotp f_i \Rightarrow X_i(g_i), \PBES^\varphi \rangle = R_{\land,\sigma}(\varphi, V)\\
& R_{\land,\sigma}(f \lor \varphi, V)          && = &&\; R_{\land,\sigma}(\varphi \lor f, V)\\
& R_{\land,\sigma}(\varphi \lor \psi, V)       && = &&\; \langle \TRUE \Rightarrow \tilde{X}(V), (\sigma\tilde{X}(V) = \varphi \lor \psi) \rangle\\
& R_{\land,\sigma}(\forall W \ldotp \varphi, V) && = &&\; \langle \textstyle\bigwedge_{i \in I^\varphi} \forall W \cup W_i \ldotp f_i \Rightarrow X_i(g_i), \PBES^\varphi \rangle\\
& ~                                            && ~ &&\; \quad \text{where } \langle \textstyle\bigwedge_{i \in I^\varphi} \forall W_i \ldotp f_i \Rightarrow X_i(g_i), \PBES^\varphi \rangle = R_{\land,\sigma}(\varphi, V \cup W)\\
& R_{\land,\sigma}(\exists W \ldotp \varphi, V) && = &&\; \langle \TRUE \Rightarrow \tilde{X}(V), (\sigma\tilde{X}(V) = \exists W \ldotp \varphi) \rangle
\end{alignat*}
```

Quantified simple formulas, such as $\forall W \ldotp f$ in a disjunctive
equation, are caught by the first rule, because every subformula is checked for
being simple before its shape is considered. The mCRL2 documentation lists them
as separate rules. Similarly, mCRL2 writes every summand with a quantifier over a
dummy variable of a singleton sort where merc uses an empty quantifier.

A newly introduced equation $\sigma\tilde{X}(V) = \psi$ always has the
connective or quantifier of $\psi$ as its *own*: an $\land$ that is not of the
shape $f \land X(e)$ makes it conjunctive, an $\exists$ makes it disjunctive, and
so on. Transforming it therefore makes progress, which is why the whole
transformation terminates.

### The algorithm

The equations are processed with a worklist. An equation introduced while
transforming another is inserted at the *front* of the worklist, so that it ends
up directly after the equation it was introduced for, which keeps related
equations together and preserves the nesting of the fixpoints:

```math algorithm
\begin{algorithmic}[1]
\Function{SRF}{$\PBES$}
  \State $\Xfalse, \Xtrue \gets$ fresh names
  \State $Q \gets$ the equations of $\PBES$, in order \Comment{a double-ended queue}
  \State $\PBES' \gets \emptyset$
  \While{$Q \neq \emptyset$}
    \State $(\sigma X(d{:}D) = \varphi) \gets \Call{PopFront}{Q}$
    \If{$\mathit{conj}(\varphi)$}
      \State $\langle \bigwedge_{i \in I} \forall W_i \ldotp f_i \Rightarrow X_i(g_i), \PBES'' \rangle \gets R_{\land,\sigma}(\varphi, d)$
    \Else
      \State $\langle \bigvee_{i \in I} \exists W_i \ldotp f_i \land X_i(g_i), \PBES'' \rangle \gets R_{\lor,\sigma}(\varphi, d)$
    \EndIf
    \State \Call{PushFront}{$Q$, $\PBES''$}
    \State $\PBES' \gets \PBES'\, (\sigma X(d{:}D) = \text{the summands above})$
  \EndWhile
  \State \Return $\PBES'\, (\mu \Xfalse = \FALSE \lor \Xfalse)\, (\nu \Xtrue = \Xtrue)$
\EndFunction
\end{algorithmic}
```

In merc the rules are implemented by `SrfBuilder::collect_summands`, which
dispatches on the shape of the subformula after checking whether it is simple.
Whether a subformula is simple is asked for every subformula at every level of
the recursion, so the answers are memoised by `SimpleExpressionCache`; since
expressions are maximally shared, the cache also answers for the subformulas
that different equations have in common.

## Pre-SRF {#pre-srf}

For generating evidence, mCRL2's `pbessolvesymbolic` uses a *pre-SRF*, in which
the conditions $f_{ij}$ may be
[pseudo-simple](counter_examples.md#pseudo-simple-formulas): they can contain
the counter-example variables `Zpos` and `Zneg`, so that the evidence still
identifies the transitions of the process. The transformation to pre-SRF uses
the rules above,
where $f$ ranges over pseudo-simple formulas, and additionally merges the simple
operands of a chain of the equation's own connective, subsuming the
corresponding rules above:

```math
\begin{align*}
R_{\lor,\sigma}\bigl(\textstyle(\bigvee_{i \in I} f_i) \lor (\bigvee_{j \in J} \varphi_j), V\bigr)
& = \bigl\langle \textstyle(\bigvee_{i \in I} f_i \land \Xtrue) \lor
\bigvee_{k \in \bigcup_{j \in J} I^{\varphi_j}} \exists W_k \ldotp (\neg \bigvee_{i \in I} f_i) \land f_k \land X_k(g_k),
\PBES^{\varphi_1} \cdots \PBES^{\varphi_{|J|}} \bigr\rangle \\
R_{\land,\sigma}\bigl(\textstyle(\bigwedge_{i \in I} f_i) \land (\bigwedge_{j \in J} \varphi_j), V\bigr)
& = \bigl\langle \textstyle\bigwedge_{i \in I} (\neg f_i \Rightarrow \Xfalse) \land
\bigwedge_{k \in \bigcup_{j \in J} I^{\varphi_j}} \forall W_k \ldotp (\bigwedge_{i \in I} f_i) \land f_k \Rightarrow X_k(g_k),
\PBES^{\varphi_1} \cdots \PBES^{\varphi_{|J|}} \bigr\rangle
\end{align*}
```

where the $f_i$ are simple. Each simple operand becomes an escape summand of its
own, and the other summands are strengthened with the negation of the simple
disjuncts (or with the simple conjuncts), so that they only apply when no escape
summand does. The simple operands are checked *without* allowing
counter-example variables, since the combined condition is copied into the
conditions of other summands as is.

## Differences in merc

merc's `pbes_to_srf`
and `pbes_to_pre_srf`
both take a `merge_simple_expressions` flag, like mCRL2, and differ from mCRL2 in
the following ways.

- **Chains are flattened for plain SRF too.** A chain of the equation's own
  connective is split into its distinct operands (`split_and`/`split_or`, which,
  like mCRL2's, return each operand once) for both forms, and with
  `merge_simple_expressions` its simple operands are merged as in the pre-SRF
  rules. mCRL2 only does this for pre-SRF, and transforms the operands of a
  plain SRF chain one by one, so it can produce the same summand more than once.
- **The one-sided rules apply without merging when the other side is an
  instantiation.** mCRL2 applies $R_{\lor,\sigma}(\varphi \land f, V)$ and its
  duals only with `merge_simple_expressions`, and otherwise introduces a new
  equation for the whole $\varphi \land f$. For $f \land X(e)$, however, that
  equation is classified exactly like the one it came from, by the exception in
  $\mathit{conj}$, and is deferred again, forever. All mCRL2 tools pass `true`,
  so this does not show there. merc always pulls out a simple side that is next
  to an instantiation.
- **Conditions are built with optimising constructors.** Conjunctions,
  disjunctions and negations of conditions absorb the constants `true` and
  `false` and double negations as they are built (see `optimized_and` and
  friends in `merc_utilities`), so the condition of $\TRUE \land X(e)$ is not
  carried along as such.
- **Trivial summands are removed.**
  `pbes_to_srf`
  finishes with
  `simplify_srf_pbes`,
  which simplifies every guard and drops the summands whose guard is $\FALSE$ in
  a disjunctive equation, or vacuous in a conjunctive one. An unconditional
  summand to $\Xtrue$ in a disjunctive equation (or to $\Xfalse$ in a
  conjunctive one) decides the equation, which is then replaced by that single
  summand, so that it no longer depends on the other, now irrelevant, summands.
- **The input must be well typed.** Both functions first call
  [`Pbes::check_well_typed`](pbes.md#well-typedness), for the reason explained
  next.

## Variable capture {#variable-capture}

The rule $R_{\lor,\sigma}(\exists W \ldotp \varphi, V)$ moves the summands of
$\varphi$ under the quantifier $\exists W$, and the one-sided rules then add the
simple $f$ from *outside* the quantifier to their conditions. This is only
correct if $f$ does not mention a variable in $W$, i.e. if $\exists W$ does not
shadow a variable that is free in $f$. Consider:

```math
\[
\begin{aligned}
\nu X(b{:}\mathbb{B}) &= Y(\FALSE) \lor (b \land \exists b{:}\mathbb{B} \ldotp Y(b)) \\
\nu Y(b{:}\mathbb{B}) &= b
\end{aligned}
\]
```

with initial state $X(\FALSE)$. The second disjunct is false, so $X(\FALSE) =
Y(\FALSE) = \FALSE$. The equation for $X$ is disjunctive, and the rule for
$\varphi \land f$ with $f = b$ produces the summand $\exists b \ldotp b \land
Y(b)$, in which the parameter $b$ has been captured by the quantifier. The
transformed equation $X(b) = Y(\FALSE) \lor \exists b \ldotp b \land Y(b)$ makes
$X(\FALSE)$ true.

This PBES is ill-typed, since the quantifier variable $b$ has the same name as a
parameter, and mCRL2's parser renames such variables. mCRL2's PBES library does
not check for it however, so the PBES can still reach `pbes2srf` when it is
constructed directly or read from a `.pbes` file. Solving it through mCRL2's SRF
transformation indeed yields `true`, whereas solving it directly yields `false`.
merc rejects it with `PbesWellTypedError::QuantifierShadowsParameter` instead.
The `write_srf_capture` example of `merc_pbes` writes this PBES in the binary
format: `cargo run -p merc_pbes --example write_srf_capture -- srf_capture.pbes`.

For pre-SRF, the merging rules for chains move conditions under quantifiers in
the same way, and the same capture occurs, for example in $\nu X(b{:}\mathbb{B})
= b \lor \exists b{:}\mathbb{B} \ldotp Y(b)$.
