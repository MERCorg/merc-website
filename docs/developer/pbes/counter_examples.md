```math_preamble
\newcommand{\TRUE}{\mathit{true}}
\newcommand{\FALSE}{\mathit{false}}
\newcommand{\Zpos}{\mathit{Zpos}}
\newcommand{\Zneg}{\mathit{Zneg}}
```
# Counter-example encoding

Solving a [PBES](pbes.md) that encodes a model checking question tells whether a
modal formula holds, but not *why*. To explain the answer in terms of the
original process, mCRL2's `lps2pbes` (and `lts2pbes`) can encode extra
information in the PBES with the `--counter-example` (`-c`) flag. Whenever the
translation of a modality refers to a transition of the process, it adds a
reference to an auxiliary propositional variable that identifies that
transition. The solver then reads the transitions that the evidence for the
solution depends on off these variables, and turns them into a witness or a
counter-example, typically as a labelled transition system.

## The encoding

<a id="def-counter-example-encoding"></a>**Definition 1 (counter-example encoding).** For every summand $i$ of the linear process, with multi-action $a_i$, the
translation introduces two propositional variables, whose names are
`Zpos_<i>_<a>` and `Zneg_<i>_<a>`, where `<i>` is the index of the summand and
`<a>` is derived from the action names. Both take the source state $d$, the
action arguments $f_i(d, e)$ and the target state $g_i(d, e)$ of a transition as
their parameters, and their equations are trivial:

```math
\[
\nu \Zpos_i(d, f, d') = \TRUE
\qquad\qquad
\nu \Zneg_i(d, f, d') = \FALSE
\]
```

so the fixpoint symbol does not matter. The translation of a box modality, a
universally quantified *must* over the transitions of summand $i$, and of a
diamond modality, an existentially quantified *may*, then wraps the translation
$\varphi$ of the formula after the modality as follows:

```math
\[
\begin{aligned}
\textit{must:} &\quad \forall e \ldotp c_i(d, e) \land \ldots \Rightarrow
  \bigl((\varphi \land \Zpos_i(d, f_i(d, e), g_i(d, e))) \lor \Zneg_i(d, f_i(d, e), g_i(d, e))\bigr) \\
\textit{may:} &\quad \exists e \ldotp c_i(d, e) \land \ldots \land
  \bigl((\varphi \lor \Zneg_i(d, f_i(d, e), g_i(d, e))) \land \Zpos_i(d, f_i(d, e), g_i(d, e))\bigr)
\end{aligned}
\]
```

where $c_i$ is the condition of the summand, and the elided part checks that the
multi-action satisfies the action formula of the modality. <a id="thm-the-encoding-preserves-the-solution"></a>**Theorem 1 (the encoding preserves the solution).** The PBES with the
counter-example encoding has the same solution as the PBES without it.

*Proof.* Since $\Zpos_i$ is $\TRUE$ and $\Zneg_i$ is $\FALSE$, both wrappers are
equivalent to $\varphi$.

The encoding does change the evidence:

- To show that a wrapper holds, the evidence must include $\varphi$ together
  with $\Zpos_i$, in the conjunction of the *must* case and in the outer
  conjunction of the *may* case. A $\Zpos_i$ vertex therefore marks a
  transition that is part of a **witness**.
- To show that a wrapper does not hold, the evidence must refute both disjuncts
  of the *must* case, or the disjunction of the *may* case, and so includes
  $\varphi$ together with $\Zneg_i$. A $\Zneg_i$ vertex therefore marks a
  transition that is part of a **counter-example**.

Because the parameters of a counter-example variable contain the whole
transition, the evidence directly yields the source state, the action with its
arguments, and the target state of every transition involved, without relating
the PBES back to the process by hand.

## Pseudo-simple formulas {#pseudo-simple-formulas}

A formula without any propositional variable instantiations is
[simple](pbes.md#simple-formulas). <a id="def-pseudo-simple-formula"></a>**Definition 2 (pseudo-simple formula).** A formula whose only instantiations are
of counter-example variables is *pseudo-simple*: as far as the solution is
concerned it is simple, since those instantiations are constants, but it still
carries the transitions that the evidence needs. Algorithms that treat simple
formulas specially can therefore either ignore the counter-example variables, at
the cost of losing evidence, or treat pseudo-simple formulas as simple. The
latter is what the [pre-SRF](srf_transformation.md#pre-srf) does: it keeps the
counter-example variables inside the conditions of its summands instead of
introducing summands for them.

## In merc

[`is_counter_example_name`](https://mercorg.github.io/merc/merc_pbes/)
recognises a counter-example variable by the `Zpos_<i>_` or `Zneg_<i>_` prefix of
its name,
`is_counter_example_positive`
tells the two apart, and
`counter_example_index`
extracts the summand index $i$. Like mCRL2, merc relies on this naming
convention: an equation is not checked to actually have the trivial right-hand
side of a counter-example equation.
