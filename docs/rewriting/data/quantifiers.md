```math_preamble
\usepackage[paperwidth=60cm,paperheight=60cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
\newcommand{\nf}{\mathrm{nf}}
\newcommand{\FV}{\mathrm{FV}}
\newcommand{\Rg}{\mathrm{Rg}}
```
# Quantifiers in the rewriter

The [`InnermostRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.InnermostRewriter.html)
of [`merc_sabre`](https://mercorg.github.io/merc/merc_sabre/index.html)
rewrites terms that contain binders, and eliminates `exists` and `forall`
while doing so with the search of [Data enumeration](enumeration.md).
This page defines
substitution on binders (Definitions 1 to 3), how a binder is rewritten
(Definition 4 and Theorems 1 and 2), how a quantifier is decided (Theorem 3),
and why the same scheme stays sound for nested quantifiers and for binders in
right-hand sides. It assumes
[Data enumeration, Definitions 1 to 4](enumeration.md#def-normal-form-under-a-substitution).

## Binders and substitution

<a id="def-binder"></a>**Definition 1 (binder).** A *binder* is a term
$Q \bar x . \varphi$ with $Q$ one of $\exists$, $\forall$, $\lambda$ or a
set or bag comprehension, bound variables $\bar x = x_1, \ldots, x_n$ and
body $\varphi$. A *quantifier* is a binder with $Q \in \{\exists, \forall\}$;
merc represents all of them as a
[`DataAbstraction`](https://mercorg.github.io/merc/merc_data/struct.DataAbstraction.html).

<a id="def-free-variables"></a>**Definition 2 (free variables).** The *free variables* of a term are
$\FV(x) = \{x\}$, $\FV(f(t_1, \ldots, t_k)) = \bigcup_i \FV(t_i)$ and
$\FV(Q \bar x . \varphi) = \FV(\varphi) \setminus \bar x$. For a substitution
$\sigma$ and a set of variables $V$, the variables that $\sigma$ introduces
for $V$ are $\Rg_V(\sigma) = \bigcup_{y \in V} \FV(\sigma(y))$, with
$\sigma(y) = y$ outside the domain of $\sigma$.

<a id="def-capture-avoiding-substitution"></a>**Definition 3 (capture-avoiding substitution).** Let
$V = \FV(Q \bar x . \varphi)$. A *renaming* of $\bar x$ for $\sigma$ is a
list of variables $\bar x' = x'_1, \ldots, x'_n$, of the same sorts, such that

1. the $x'_i$ are pairwise distinct;
2. every $x'_i$ is $x_i$, or occurs neither in $V$ nor in $\bar x$;
3. no $x'_i$ is in $\Rg_V(\sigma)$.

Then $(Q \bar x . \varphi)\sigma = Q \bar x' . \varphi(\rho \rhd \sigma)$,
where $\rho$ maps each $x_i$ to $x'_i$ and
$(\rho \rhd \sigma)(y)$ is $\rho(y)$ for $y \in \bar x$ and $\sigma(y)$
otherwise.

The bound variables are looked up in $\rho$ *instead of* $\sigma$: this is
what makes $x_i$ shadow an image that $\sigma$ has for the same name, also
when $x'_i = x_i$. Condition 3 is what prevents capture: a variable
introduced by $\sigma$ must not end up bound.

<a id="thm-alpha-equivalence"></a>**Theorem 1 (α-equivalence).** Any two renamings of $\bar x$ for
$\sigma$ give α-equivalent terms, which are equal in every model under every
valuation.

This is the standard substitution lemma of the λ-calculus. Proved on paper
only; merc's Lean development covers first-order rewriting, without binders.

## Rewriting a binder

<a id="def-binder-normal-form"></a>**Definition 4 (rewriting a binder).** The rewriter computes
$\nf((Q \bar x . \varphi)\sigma)$ as follows, for a $\sigma$ whose images are
normal forms:

```math algorithm
\begin{algorithmic}[1]
\Function{RewriteBinder}{$Q \bar x . \varphi, \sigma$}
  \State $V \gets \FV(Q \bar x . \varphi)$
  \For{$i \gets 1, \ldots, n$}
    \If{$x_i \in \Rg_V(\sigma)$} \State $x'_i \gets$ a fresh variable named $x_i$@$k$ \Else \State $x'_i \gets x_i$ \EndIf
  \EndFor
  \State $\psi \gets \nf(\varphi(\rho \rhd \sigma))$ \Comment{with $\bar x'$ free}
  \If{$Q \in \{\exists, \forall\}$ and $\Call{Decide}{Q, \bar x', \psi} = r$} \State \Return $r$ \EndIf
  \State \Return $Q \bar x' . \psi$
\EndFunction
\end{algorithmic}
```

`Decide` is described in [Deciding a quantifier](#deciding-a-quantifier).
Lambdas and comprehensions are only rebuilt over their rewritten body, since
β-reduction is not implemented.

<a id="thm-binder-body"></a>**Theorem 2 (rewriting the body).** The renaming in Definition 4
satisfies the conditions of Definition 3, so
$Q \bar x' . \psi$ is equal to $(Q \bar x . \varphi)\sigma$ in every model
under every valuation.

*Proof idea.* A variable is renamed exactly when it violates condition 3, so
the variables kept satisfy it, and fresh names are checked against $V$,
$\bar x$ and $\Rg_V(\sigma)$, which gives conditions 1 to 3 for the others.
The body $\varphi(\rho \rhd \sigma)$ and its normal form $\psi$ are equal
under every valuation, in particular under every valuation of $\bar x'$, by
[Conditional rewriting, Theorem 1](../rewriters/conditional-rewriting.md#thm-soundness),
so the two binders are equal. Proved on paper only.

### Choices specific to merc

- **Rename only on capture.** The common case is a binder rewritten under an
  empty substitution, such as every quantifier of a closed term, and then no
  variable is renamed. A renamed binder is a different term, so renaming
  eagerly would also break the maximal sharing of
  [Terms, Definition 2](../terms/aterms.md#def-maximal-sharing) between otherwise
  equal normal forms, and any cache keyed on them.
- **One scope for shadowing and renaming.** The body is rewritten under
  $\rho \rhd \sigma$ literally: the scope of a binder maps *every* bound
  variable, also an unrenamed one to itself, and looks up every other variable
  in $\sigma$. A separate "shadowed" case is not needed. $\sigma$ is
  type-erased behind `dyn`, since the body can contain binders of its own,
  which would otherwise instantiate an ever longer chain of substitution types.
- **The range is computed once and kept.** Computing $\Rg_V(\sigma)$ exactly
  would need the free variables of the binder. Instead
  [`RewriteSubstitution::range`](https://mercorg.github.io/merc/merc_sabre/utilities/trait.RewriteSubstitution.html#method.range)
  collects the variables that occur in any of its images, an
  over-approximation that only costs a needless renaming. By default it
  traverses the images, which only happens when a binder is reached, and a
  substitution only has to list its bindings. The scope of a binder instead
  keeps the range of $\sigma$ extended with its fresh variables, so a nested
  binder does not traverse the images of $\sigma$ again. An identity entry
  $y \mapsto y$ is skipped: it introduces $y$, which only matters to a binder
  of $y$, and there $y$ is not in $V$. Without this, the identity entries of
  $\rho$ would rename the inner binder of `forall x . exists x . φ` for no
  reason.
- **Fresh names come from the symbol pool.** A fresh variable is named
  `x@k`, with `k` counted per rewriter. A variable's name is a symbol, and a
  live term keeps its symbols in the pool of
  [Terms](../terms/aterms.md#terms-and-maximal-sharing). The name is therefore created
  only if the pool does not contain it yet, in one atomic step, which makes
  it occur in no live term: not in the body or an image, where the binder
  would capture it, and not in a term from another rewriter or read from a
  file written by an earlier run. No term is traversed, and two threads never
  receive the same name.

## Deciding a quantifier

`Decide` is the
[`Enumerator`](https://mercorg.github.io/merc/merc_sabre/trait.Enumerator.html)
trait of `merc_sabre`, given the rewritten body $\psi$ with the bound
variables free. The default,
[`NoQuantifierEnumerator`](https://mercorg.github.io/merc/merc_sabre/struct.NoQuantifierEnumerator.html),
keeps every quantifier. The implementation of
[`merc_enumerate`](https://mercorg.github.io/merc/merc_enumerate/index.html)
proceeds as follows.

1. Drop the bound variables that do not occur in $\psi$, which is valid since
   every sort is non-empty. If none is left, the result is $\psi$.
2. Split the rest into the variables $\bar z$ of an enumerable sort
   ([Data enumeration, Definition 2](enumeration.md#def-enumerability)) and
   the others $\bar y$. If $\bar z$ is empty, the quantifier is kept.
3. Run [the search](enumeration.md#the-search) on $\bar z$ and $\psi$, looking
   for a witness of $\exists$ or a counterexample of $\forall$.

| Search outcome | $\exists$ | $\forall$ |
|---|---|---|
| witness or counterexample found | `true` | `false` |
| exhausted, every leaf rejected | `false` | `true` |
| exhausted, with undecided leaves $\psi_1, \ldots, \psi_k$ | $\exists \bar y . \nf(\psi_1 \lor \cdots \lor \psi_k)$ | $\forall \bar y . \nf(\psi_1 \land \cdots \land \psi_k)$ |
| a limit reached (only over an infinite sort), or a sort met that is not enumerable | $\exists \bar y \bar z . \psi$ | $\forall \bar y \bar z . \psi$ |

The variables $\bar y$ are split off because the search abandons the whole
goal as soon as it has to expand a variable whose sort is not enumerable.
Handed all of $\bar x'$, a search over `exists x: Real, p: Pos . φ` would
therefore keep the quantifier, also when `p` alone could be eliminated.
Quantifiers of the same kind commute, so the search runs on
$\exists \bar z . \psi$ only, and $\bar y$ stays bound around whatever it
leaves. In the first two rows $\bar y$ disappears with the
quantifier: the deciding leaf, and in the second row every branch, is the
literal itself, so the result holds for every value of $\bar y$.

In the third row, duplicate leaves are dropped before they are combined, the
variables of $\bar y$ that no longer occur are dropped after, and the binder
disappears when none is left. A leaf is undecided when its body is ground in
$\bar z$ but still depends on other variables: those of $\bar y$, of an
enclosing quantifier, or a mapping without equations for its arguments.

<a id="thm-decide"></a>**Theorem 3 (deciding).** In every row of the table, the result is equal to
$Q \bar x' . \psi$ in every model under every valuation.

*Proof idea.* Write $\exists \bar x' . \psi$ as
$\exists \bar y . \exists \bar z . \psi$, and dually for $\forall$. The first
row is a witness ([Data enumeration, Definition 4](enumeration.md#def-witness)).
An exhausted search reached no limit, so by
[Data enumeration, Theorems 1 and 2](enumeration.md#thm-search-soundness)
every ground substitution for $\bar z$ either extends a rejected work item or
is one of the undecided leaves, and $\exists \bar z . \psi$ is the disjunction
of the leaf bodies $\psi_i$, which is `false` when there are none. The last
row keeps the quantifier. Proved on paper only.

Two examples, both from the tests of `merc_enumerate`:

- `exists y: Bool . (y && c) || (!y && d)` becomes `c || d`: both leaves are
  undecided, as `c` and `d` are mappings without equations.
- `exists x: Real, p: Pos . p == 1 && x > 4` becomes
  `exists x: Real . x > 4`. `Real` is not enumerable, so only `p` is searched,
  and its one undecided leaf, `p = 1`, leaves the body `x > 4`.

The [one-point rule](enumeration.md#the-one-point-rule) is not applied here;
it is a preprocessing step for whoever builds the quantifier.

## Nested quantifiers

In $Q_1 \bar x . \ldots Q_2 \bar y . \varphi \ldots$, the inner quantifier is
reached first, while the outer body is rewritten, with $\bar x$ free. Its
search then has one of the outcomes above:

- it is decided, or eliminated by its undecided leaves, and the outer search
  never sees a binder; or
- it reaches a limit, or no variable is enumerable, and $Q_2 \bar y . \psi$
  stays in the outer body.

The first case is where the undecided leaves of the third row of the table
pay off. With $\bar x$ free, the leaves of the inner search typically depend
on $\bar x$ and are undecided, and the inner quantifier is replaced by their
combination. In
`forall x: Nat . x < 3 => exists y: Nat . y < 3 && x + y == 2`, the branches
for `y` of at least 3 are rejected by `y < 3`, and the leaves `y = 0`, `1`
and `2` leave the inner quantifier as

```
x == 2 || x + 1 == 2 || x + 2 == 2
```

The outer search then rewrites this disjunction under each candidate for
`x`, and never searches `y` again. This makes rewriting
[faster](../../benchmarks/rewriting.md#nested-quantifiers) than keeping the inner
quantifier, as the inner search runs once instead of once per value of `x`.

In the second case the outer search rewrites that body under each candidate
$x := t$, as a substitution, so
`RewriteBinder` is applied to the inner binder again under $x \mapsto t$ and
the inner quantifier is decided with the concrete value.

Three things make this sound.

- **Every substitution goes through `RewriteBinder`.** The candidate $t$ may
  contain a fresh variable of the outer search, `v3` say, and a user may well
  have named the inner bound variable `v3`. Renaming (Theorem 2) applies to
  the enumerator's substitutions exactly as to any other, so the inner binder
  is renamed apart instead of capturing it.
- **One frame per running search.** The rewriter keeps a stack of
  [`EnumeratorFrame`](https://mercorg.github.io/merc/merc_enumerate/struct.EnumeratorFrame.html)s
  and takes a frame off it for as long as its search runs, so a search that
  starts inside a rewrite call of another one never touches the outer queue
  or bindings.
- **One fresh-variable generator, never reset in between.** The inner body
  contains the outer search's fresh variables free. Since both searches draw
  from the same
  [`FreshVariableGenerator`](https://mercorg.github.io/merc/merc_enumerate/struct.FreshVariableGenerator.html),
  the inner search never generates one of them again, which would merge two
  distinct unknowns.

## Binders in right-hand sides

The innermost rewriter meets a binder in two places, and applies
`RewriteBinder` to both. They differ in the substitution, which is always the
one that gives the binder's free variables their values.

- **A binder of the input term.** Rewriting `rewrite_with(t, σ)` replaces a
  variable of $t$ by its image under $\sigma$ only when it reaches that
  variable. A binder of $t$ is reached before any variable in it, so its body
  is rewritten under $\sigma$.
- **A binder of a right-hand side.** A rule $l = r$ applied to $l\tau$ yields
  $r\tau$, where the matching substitution $\tau$ maps the variables of the
  rule to subterms of the input term. The innermost rewriter does not build
  $r\tau$ first: it builds $r$ bottom-up from the normal forms of those
  subterms. For a binder $b$ in $r$, it rewrites $b$ under $\tau$, with the
  normal forms as images. $\sigma$ plays no part here, since the matched
  subterms were already substituted when they were rewritten.

The right-hand side is compiled once per rule. A binder $b$ in it becomes the
closed template $\lambda \bar u . b$ over its free variables $\bar u$, in the
order of their first occurrence, and the $u_i$ are compiled before it like the
arguments of a symbol, so that their values are on top when the binder is
reached. The binder is then rewritten under $\bar u \mapsto$ values. The
template is only an encoding and is never β-reduced: it is a term, so it can be
kept in the compiled right-hand side, and its bound variables record which
variable each value is for.

For example, `h(x) = exists y . g(x, y)` is compiled to the template
`lambda x . exists y . g(x, y)` with one value, for `x`. Rewriting `h(y)`,
where `y` is free, gives that value `y`, and rewrites `exists y . g(x, y)`
under $x \mapsto y$. Since `y` is in the range, the bound `y` is renamed to
`y@0` and the result is `exists y@0 . g(y, y@0)`, rather than the captured
`exists y . g(y, y)`.

Only the innermost rewriter and the
[`JittyRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.JittyRewriter.html),
which share its machine ([Just-in-time rewriting](../rewriters/jitty.md#one-machine-for-both-rewriters)),
do this. The jitty rewriter rewrites the free variables of such a binder before
the rule applies ([Just-in-time rewriting, Definition 2](../rewriters/jitty.md#def-needed-argument)),
so they are normal forms here too. The
[`SabreRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.SabreRewriter.html)
and [`NaiveRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.NaiveRewriter.html)
drop every rewrite rule with a binder in its right-hand side.

## Known gaps

- **Fresh enumerator variables and free variables of the input.** The
  enumerator names its fresh variables `<prefix><n>` and avoids only the names
  it was seeded with. Renaming protects against a *bound* variable of that
  name, but a *free* variable of the rewritten term with that name is merged
  with the fresh one. A caller that rewrites open terms has to seed the
  generator with their names; using `@` names, as the binder renaming does,
  would remove that obligation.
- **No β-reduction.** A lambda is rebuilt over its rewritten body, and a
  lambda in head position is not applied, see
  [Data enumeration, Not yet implemented](enumeration.md#not-yet-implemented).
- **No `where` clauses.** The innermost rewriter panics on a `where` clause,
  and the set automaton drops every rule that contains one.
- **Polarity of the residuals.** The undecided leaves are combined and
  rewritten, but not split again: a disjunction of residuals under
  $\exists \bar y$ is the same shape that hides one-point equations from
  [the static fixpoint](enumeration.md#gap-a-top-level-connective-of-the-wrong-polarity).
