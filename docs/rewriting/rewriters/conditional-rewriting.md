# Conditional rewriting

This page defines conditional rewriting as merc's rewriters implement it
(Definitions 1 to 3) and states the theorems on it that are proved in Lean
(Theorems 1 to 4). In merc, a system is a
[`RewriteSpecification`](https://mercorg.github.io/merc/merc_sabre/struct.RewriteSpecification.html)
of [`Rule`](https://mercorg.github.io/merc/merc_sabre/struct.Rule.html)s with
[`Condition`](https://mercorg.github.io/merc/merc_sabre/struct.Condition.html)s,
and the engines of [`merc_sabre`](https://mercorg.github.io/merc/merc_sabre/index.html)
compute its normal forms; [The set automaton](set-automaton.md) describes how
[`SabreRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.SabreRewriter.html)
finds the subterms to rewrite. It assumes [Terms, Definitions 1 and 2](aterms.md#def-term).

## Rewrite systems

<a id="def-conditional-rewrite-system"></a>**Definition 1 (conditional rewrite system).** A *conditional rewrite rule*
$c_1 \land \dots \land c_k \to l = r$ over a many-sorted signature has a
left-hand side $l$ and right-hand side $r$ of the same sort, and conditions
$c_i$ of the form $u_i \to v_i$. A *conditional rewrite system* is a set of such
rules.

<a id="def-rewriting"></a>**Definition 2 (rewriting).** A term $t$ *rewrites* to $t'$ if some subterm of $t$
is an instance $l\sigma$ of the left-hand side of a rule whose conditions hold
under $\sigma$, in that each $u_i\sigma$ rewrites in zero or more steps to
$v_i\sigma$, and $t'$ replaces that subterm by $r\sigma$. A *normal form* is a
term that does not rewrite. The system is *terminating* if no term admits an
infinite sequence of rewrite steps.

<a id="def-model"></a>**Definition 3 (model).** An algebra $A$ for the signature is a *model* of the
system if every rule holds in $A$ under every valuation that satisfies its
conditions. Its normal forms are *injective* in $A$ if distinct normal forms of
the same sort have distinct values; this combines sufficient completeness
(normal forms are constructor terms) with no confusion (the model has no junk).

The data equations of a specification are such a system, with the intended
interpretation of the data types as model, and a rewriter computes normal forms
of data expressions. [Lowering](lowering.md) produces this system from the data
equations of a specification.

## Soundness, termination and confluence

<a id="thm-soundness"></a>**Theorem 1 (soundness).** If $A$ is a model, then $t$ rewriting to $t'$ in any
number of steps implies that $t$ and $t'$ have the same value in $A$, under every
valuation.

<a id="thm-termination"></a>**Theorem 2 (termination).** A system is terminating if some measure into a
well-founded order decreases with every rewrite step. In particular, it is
terminating if there is an algebra whose operations are strictly monotone in
every argument, over a well-founded order, in which every rule strictly
decreases the value of its left-hand side to that of its right-hand side.

<a id="thm-confluence"></a>**Theorem 3 (confluence).** If $A$ is a model, the system is terminating and its
normal forms are injective in $A$, then the system is confluent.

<a id="thm-unique-normal-forms"></a>**Theorem 4 (unique normal forms).** Under the assumptions of Theorem 3, every term
has exactly one normal form, and by Theorem 1 its value in $A$ is the value of the
term: the rewrite system computes the model.

Theorems 1 to 4 are proved in Lean, without `sorry`, in the
[`MercLib/Rewriting`](https://github.com/MERCorg/merc-verified/tree/main/MercLib/Rewriting)
library of merc-verified. Its definitions are stated in human-vetted files, and
the theorems are in the generated proof files:

| theorem | Lean |
|---|---|
| Theorem 1 | [`Steps.eval_eq`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Rewriting/Proofs/Soundness_Proofs.lean), for [`Model`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Rewriting/Soundness.lean) |
| Theorem 2 | [`terminating_of_measure` and `terminating_of_interpretation`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Rewriting/Proofs/Termination_Proofs.lean), for [`Terminating`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Rewriting/Rewrite.lean) and [`Decreasing`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Rewriting/Termination.lean) |
| Theorem 3 | [`confluent_of_model`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Rewriting/Proofs/Confluence_Proofs.lean), for [`NormalFormsInjective`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Rewriting/Confluence.lean) |
| Theorem 4 | [`existsUnique_normalForm`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Rewriting/Proofs/Confluence_Proofs.lean) |
