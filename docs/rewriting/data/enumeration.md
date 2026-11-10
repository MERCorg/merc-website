```math_preamble
\usepackage[paperwidth=60cm,paperheight=60cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
\newcommand{\nf}{\mathrm{nf}}
\newcommand{\FV}{\mathrm{FV}}
\newcommand{\Sol}{\mathrm{Sol}}
\newcommand{\T}{\mathcal T}
```
# Data enumeration

Several parts of merc have to *close* an open data expression: pick concrete
values for a set of free variables until a Boolean condition is decided.
Deciding a quantifier needs one witness for $\exists$ (or one counterexample
for $\forall$), and generating the successors of an LPS summand
`sum d: D . c(d) -> a(d) . P(d)` needs every value of `d` that makes the
condition true. The [`merc_enumerate`](https://mercorg.github.io/merc/merc_enumerate/index.html)
crate implements both with one search, driven by any
[`RewriteEngine`](https://mercorg.github.io/merc/merc_sabre/trait.RewriteEngine.html).
This page defines what that search computes (Definitions 1 to 4), describes
the algorithm and its correctness (Theorems 1 and 2), and the one-point rule
that callers apply before searching. [Quantifiers in the rewriter](quantifiers.md)
describes how the rewriter uses the search to eliminate `exists` and `forall`.
It assumes [Conditional rewriting, Definitions 1 to 3](../rewriters/conditional-rewriting.md#def-conditional-rewrite-system).

## Definitions

Fix a data specification with sorts $S$ and, for every sort $s \in S$, a set
of constructors $C_s$. Write $\T_C(s)$ for the set of *ground constructor
terms* of sort $s$: terms built from constructors only, without variables.

<a id="def-normal-form-under-a-substitution"></a>**Definition 1 (normal form under a substitution).** A *substitution*
$\sigma$ maps finitely many variables to terms; $t\sigma$ replaces every free
occurrence of a variable $x$ in the domain of $\sigma$ by $\sigma(x)$, renaming
binders apart where needed ([Quantifiers in the rewriter, Definition 3](quantifiers.md#def-capture-avoiding-substitution)).
Write $\nf(t)$ for a normal form of $t$ ([Conditional rewriting, Definition 2](../rewriters/conditional-rewriting.md#def-rewriting)).
The term $t$ may be open: a variable of $t$ only matches a variable of a
left-hand side, so it behaves as an unknown constant. A rewriter computes
$\nf(t\sigma)$ for a substitution whose images are normal forms, and splices
those images in without rewriting them again; this is
[`RewriteEngine::rewrite_with`](https://mercorg.github.io/merc/merc_sabre/trait.RewriteEngine.html#method.rewrite_with).

Throughout, the rewrite system is assumed to be sound for the specification
([Conditional rewriting, Theorem 1](../rewriters/conditional-rewriting.md#thm-soundness)):
$t$ and $\nf(t)$ are equal in every model, under every valuation of their free
variables.

<a id="def-enumerability"></a>**Definition 2 (enumerability).** A sort $s$ is *finite* when $\T_C(s)$ is
finite, *infinite enumerable* when $\T_C(s)$ is infinite, and *not
enumerable* when $C_s = \emptyset$ (an abstract sort such as `Real`), when
every constructor of $s$ needs an argument of a non-enumerable sort, or when
$s$ is a function sort. merc computes this classification once per
specification, as the
[`SortEnumerability`](https://mercorg.github.io/merc/merc_enumerate/enum.SortEnumerability.html)
of each sort's
[`EnumerationPlan`](https://mercorg.github.io/merc/merc_enumerate/struct.EnumerationPlan.html).

<a id="def-solutions"></a>**Definition 3 (solutions).** Let $\bar x = x_1, \ldots, x_n$ be variables of
sorts $s_1, \ldots, s_n$ and $\varphi$ a term of sort `Bool`. A *ground
substitution* for $\bar x$ maps each $x_i$ to a term in $\T_C(s_i)$. The
*solutions* of $\varphi$ are

```math
$$
\Sol(\bar x, \varphi) = \{\, \sigma \mid \sigma \text{ a ground substitution for } \bar x,\ \nf(\varphi\sigma) = \mathit{true} \,\}.
$$
```

<a id="def-witness"></a>**Definition 4 (witness).** For $\exists \bar x . \varphi$ a *witness* is a
ground substitution $\sigma$ with $\nf(\varphi\sigma) = \mathit{true}$. For
$\forall \bar x . \varphi$ a *counterexample* is one with
$\nf(\varphi\sigma) = \mathit{false}$. A witness decides the quantifier to
$\mathit{true}$, a counterexample to $\mathit{false}$, and the absence of
either over all ground substitutions decides it the other way.

These are the two operations the crate offers:
[`Enumerator::enumerate`](https://mercorg.github.io/merc/merc_enumerate/struct.Enumerator.html#method.enumerate)
reports every element of $\Sol(\bar x, \varphi)$, and
[`Enumerator::find_witness`](https://mercorg.github.io/merc/merc_enumerate/struct.Enumerator.html#method.find_witness)
searches for a single witness or counterexample.

merc assumes that every sort is non-empty. This is what makes it
valid to drop a bound variable that does not occur in the body:
$\exists x . \varphi \equiv \varphi$ when $x \notin \FV(\varphi)$ only holds if
the sort of $x$ has an element.

## The search

The search manipulates *work items* $(R, \psi, \beta, d)$: the variables $R$
that are still free, the body $\psi$ rewritten under the bindings so far, the
bindings $\beta$ themselves, and the constructor depth $d$. A variable of a
finite sort is replaced by each of its elements at once. A variable of an
infinite sort is replaced by each constructor applied to *fresh* variables,
which are appended to $R$ and expanded later. The body decides a branch as
soon as it rewrites to the literal that rejects it, even while some variables
are still free.

```math algorithm
\begin{algorithmic}[1]
\Function{Search}{$\bar x, \varphi, \mathit{accept}$}
  \State $\mathit{reject} \gets \neg\mathit{accept}$
  \State $Q \gets [(\bar x, \nf(\varphi), \emptyset, 0)]$ \Comment{a FIFO queue}
  \While{$Q \neq []$}
    \State $(R, \psi, \beta, d) \gets \Call{PopFront}{Q}$
    \If{$\psi = \mathit{reject}$} \State \textbf{continue} \EndIf
    \If{$R = []$}
      \If{$\psi = \mathit{accept}$} \State \Call{Report}{$\beta$} \Else \State record $\psi$ as an undecided leaf \EndIf
      \State \textbf{continue}
    \EndIf
    \State $x \gets \Call{Head}{R}$, $R' \gets \Call{Tail}{R}$
    \If{the sort $s$ of $x$ is finite}
      \For{$t \in \T_C(s)$} \State \Call{PushBack}{$Q, (R', \nf(\psi[x := t]), \beta[x := t], d)$} \EndFor
    \Else
      \For{$c : s_1 \times \cdots \times s_k \to s \in C_s$}
        \State $y_1, \ldots, y_k \gets$ fresh variables of sorts $s_1, \ldots, s_k$
        \State $t \gets \nf(c(y_1, \ldots, y_k))$
        \State \Call{PushBack}{$Q, (R' \mathbin{+\!\!+} [y_1, \ldots, y_k], \nf(\psi[x := t]), \beta[x := t], d + 1)$}
      \EndFor
    \EndIf
  \EndWhile
\EndFunction
\end{algorithmic}
```

For `enumerate`, $\mathit{accept}$ is `true` and every leaf is reported. For
`find_witness` on $\exists$ it is `true` and the search stops at the first
report; on $\forall$ it is `false`, so the search looks for a counterexample.

<a id="thm-search-soundness"></a>**Theorem 1 (soundness).** Every reported $\beta$ is in
$\Sol(\bar x, \varphi)$ (for $\mathit{accept} = \mathit{true}$), and no
ground substitution that extends the bindings of a pruned work item is.

*Proof idea.* A work item's body is $\nf(\varphi\beta)$ for its bindings
$\beta$, since each step rewrites the previous normal form under one more
binding, and by soundness of $\nf$ that equals $\nf$ of the substituted
original. A leaf binds every variable, so its body decides $\varphi\beta$. A
pruned body is already the rejecting literal, and every instance of a literal
is that literal. Proved on paper only.

<a id="thm-search-fairness"></a>**Theorem 2 (fairness).** Every ground substitution for $\bar x$ is
the bindings of some leaf, or extends those of a pruned work item, after
finitely many iterations.

*Proof idea.* A ground substitution is reached along a finite path of
expansions: every expansion removes the head of $R$, and the fresh variables
it appends are expanded once the finitely many variables ahead of them are, so
a ground term of finite depth is built after finitely many expansions. The
queue is first-in first-out and every expansion pushes finitely many items,
so each item on that path is popped after finitely many iterations. This is
what makes `enumerate` complete on an infinite sort, and makes
`find_witness` find any witness that exists, given enough budget. Proved on
paper only.

### Choices specific to merc

- **Only `find_witness` is bounded.** Its search stops after
  [`EnumerationLimits`](https://mercorg.github.io/merc/merc_enumerate/struct.EnumerationLimits.html)
  `max_items` work items, and does not expand a branch past `max_depth`.
  `enumerate` is never bounded, because a truncated set of `sum` values would
  silently under-approximate the state space. Bounding `sum` enumeration is
  left to its caller, which has to report the truncation.
- **A search over finite sorts is not bounded.** When every searched
  variable has a finite sort, no fresh variables are
  introduced and the search ends after at most $\prod_i |\T_C(s_i)|$ leaves,
  so `find_witness` ignores the limits and always decides. Without it, a quantifier such as
  $\forall b_1, \ldots, b_{12} : \mathit{Bool} . \varphi$ is left undecided
  as soon as its $2^{12}$ assignments exceed `max_items`, although deciding it
  takes a few milliseconds.
- **The limits are fixed for the lifetime of an enumerator.** The summand and
  quantifier caches assume that the same inputs produce the same solutions in
  the same order, which an adaptive bound would break.
- **An undecided leaf is not an exhausted search.** A ground body can still
  rewrite to neither `true` nor `false`, for example when it applies a mapping
  that has no equation for those arguments, or when it mentions a variable
  that is free in the goal, such as that of an enclosing quantifier. The
  search then reports
  [`Outcome::Undecided`](https://mercorg.github.io/merc/merc_enumerate/enum.Outcome.html#variant.Undecided)
  with that body, and only the caller knows whether a partial result set is
  acceptable. [Quantifiers in the rewriter](quantifiers.md#deciding-a-quantifier)
  uses the undecided leaves to simplify the quantifier instead.
- **Constructor values are rewritten before they are substituted.** A
  constructor application need not be a normal form: under the
  [machine-word encoding](machine-numbers.md) of `Nat`, `@succ_nat` applied to
  a digit still rewrites. `rewrite_with` splices substitution images in
  without rewriting them (Definition 1), so they must already be normal forms.
- **Finite sorts are materialised once.** The elements of a finite sort are
  computed on first use, in normal form, and cached for the rest of the run.
- **One shared context, one frame per search.** The sort plans, the limits,
  the cache of finite sorts and the fresh-variable generator are shared, and
  the queue and bindings live in an
  [`EnumeratorFrame`](https://mercorg.github.io/merc/merc_enumerate/struct.EnumeratorFrame.html).
  A search can therefore run while another is suspended inside a rewrite
  call, which is what nested quantifiers need. Because the generator is
  shared and not reset in between, the fresh variables of the inner search
  differ from those of the outer one, which occur free in the inner body.

## The one-point rule

The cheapest variable to close is one the body already fixes. The
*one-point rule* removes such a variable without searching, by the
identities

```math
$$
\exists x . (x = e \wedge \varphi) \equiv \varphi[x := e]
\qquad
\forall x . (x \neq e \vee \varphi) \equiv \varphi[x := e]
\qquad
\text{provided } x \notin \FV(e).
$$
```

It is the degenerate, single-step case of narrowing: there is no unifier to
compute, only a conjunct (or disjunct) to read. Note the polarity. Reading
$x = e$ off a conjunct is only valid under $\exists$. Under $\forall$ it would
narrow the domain to the single point $e$, and the rule has to read a
disjunct $x \neq e$ instead. merc therefore recognises different shapes for
each quantifier:

| Quantifier | Splits on | One-point shapes |
|---|---|---|
| $\exists$, and `sum` | `&&` | `x == e`, `e == x` |
| $\forall$ | `\|\|` | `x != e`, `x == e => ψ`, `!(x == e)` |

The last two $\forall$ shapes are equivalent to `x != e || ψ` and `x != e`,
so they are recognised as they are rather than first rewritten to `!=`.

The rule is a preprocessing step that the caller is responsible for, available as
[`simplify_one_point`](https://mercorg.github.io/merc/merc_enumerate/fn.simplify_one_point.html)
for a `sum` condition or a quantifier body. Neither the enumerator nor the
rewriter applies it, so a search enumerates exactly the variables it is given,
and the cost of looking for one-point shapes is paid once rather than for
every quantifier the rewriter reaches.

### A static fixpoint

The rule is applied to the goal as given. merc splits the normalised body
into its top-level operands, takes the first one that fixes a still-free
variable, substitutes, rewrites, and repeats until none is left. Because it
repeats, a chain such as

```
n == 5 && m == n
```

resolves without search: binding `n` turns the second conjunct into
`m == 5`, which the next iteration picks up.

### Gap: a one-point conjunct exposed during the search

The fixpoint only looks at the body as given. A conjunct that
only takes the shape `x == e` after another variable has been bound by the
search is invisible to it. Take:

```
map goal: Nat # Nat -> Bool;
var n, m: Nat;
eqn goal(n, m) = (n < 2) && if(n == 0, m == 50, m == 60);
```

Neither branch of the `if` is a top-level conjunct, so both `n` and `m` are
searched. The search binds `n` to `0` almost immediately, and at that point
the body rewrites to the plain conjunct `m == 50`. Nothing re-applies the rule
there: the search instead counts `m` up from `0` until it reaches `50`.

A *dynamic* rule, re-applied after every expansion, would pick up `m == 50` at
once; [Rewriting benchmarks, One-point rule](../../benchmarks/rewriting.md#one-point-rule)
counts the difference on this goal. merc does not implement it: it would put the rule
back inside the search, and re-splitting the body on every queue pop is a cost
every search pays, while the gain only appears for a conjunct hidden behind a
non-`&&` connective and exposed by binding an unrelated variable.

### Gap: a top-level connective of the wrong polarity

The split only flattens the connective that matches the quantifier: `&&`
under $\exists$ and `||` under $\forall$. A goal such as

```
exists x, y: Nat . (x == 1 && P(y)) || (x == 2 && Q(y))
```

has a one-point conjunct in each disjunct, but both are hidden behind the
`||`, so the search enumerates `x` and `y` jointly. Dually, under $\forall$ a
top-level `&&` hides the disequations of its operands. The fix is to first
split the goal itself by polarity, using
$\exists \bar x . (\varphi \vee \psi) \equiv (\exists \bar x . \varphi) \vee (\exists \bar x . \psi)$
and $\forall \bar x . (\varphi \wedge \psi) \equiv (\forall \bar x . \varphi) \wedge (\forall \bar x . \psi)$,
and to prepare each part separately. That turns one goal into a set of
sub-goals, which is a larger change than the preprocessing it would improve,
so it waits for evidence that real conditions have this shape.

### Variable order

The variables are expanded in the order the caller declared them. merc
briefly ranked them first, preferring a variable that is the only free one
left in some conjunct, since binding it lets the search decide that conjunct
one step earlier. On a targeted goal this lowered the `max_items` needed by
`find_witness` from 22 to 18. The ranking only reordered the original
variables, never the fresh variables introduced at each expansion, so every
level past the first used the default order anyway. It was removed as not
worth its code. The last version is commit `0f8f1d48` in the merc repository.
Reviving it only makes sense together with re-ranking the fresh variables at
every level.

## Bindings along a branch

The search is breadth-first, so many partial branches are outstanding at
once, each extending a shared prefix of the bindings chosen so far. Storing an
owned map per work item would copy that prefix on every expansion, so merc
keeps the bindings as a linked list of `(variable, value)` nodes in one arena
owned by the search frame. Extending a branch is a push, and every sibling
that shares the prefix stays valid. The arena is cleared rather than dropped
between searches, so a caller that drives many searches through one
enumerator, such as `sum` successor generation, reuses its capacity.

The list is a *triangular* substitution, not a general one. A variable's
value may mention variables bound later in the same list, such as
$v \mapsto c(y_1, y_2)$ where $y_1, y_2$ were introduced to expand $v$.
Resolving a finished branch therefore substitutes along the list recursively,
and remembers the subterms it found to contain no bound variable so that it
does not traverse them again. A variable that is not bound along the list is
left in place: it is free in the goal, such as the variable of an enclosing
quantifier that a one-point equation equated a searched variable with. Each
resolved value is rewritten once at the end, for the same reason constructor
values are rewritten before substitution: substituting normal forms into a
constructor can leave a redex (`@succ_nat` applied to a machine-word digit),
and the values handed back to a caller are spliced into further rewrite calls
as substitution images.

## Testing against a second implementation

[`NaiveEnumerator`](https://mercorg.github.io/merc/merc_enumerate/struct.NaiveEnumerator.html)
plays the same role for the enumerator as
[`NaiveRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.NaiveRewriter.html)
does for the rewrite engines. It materialises every ground term of each
variable's sort up to a size bound, substitutes all variables at once, and
rewrites once per combination: no incremental normalisation, no pruning, and
no fairness scheme to get wrong. Random goals are run through both
enumerators and their solution *sets* compared.

Two things keep this cheap enough to run 200 goals per invocation. Goals are
built through the [`merc_data`](https://mercorg.github.io/merc/merc_data/index.html)
API rather than as source text, so neither the parser nor the type checker
runs per goal. And the rewriters are built once, outside the loop: building an
`InnermostRewriter` compiles a
[`SetAutomaton`](https://mercorg.github.io/merc/merc_sabre/struct.SetAutomaton.html)
over every equation of the specification, including the whole built-in
library (331 equations even for a specification with one small custom sort).
Rebuilding it per goal took over a CPU-minute for 200 goals, against well
under a second with shared rewriters.

## Not yet implemented

- **Pruning by the set automaton.** Before expanding a variable that is an
  argument of a defined function, skip the constructors for which no rewrite
  rule could ever match, such as `[]` in `head(l) == 3`. This has to stay
  conservative, because a stuck term is a legal normal form.
- **Function sorts and finite sets.** A finite function sort can be
  enumerated as lambda terms over if-then-else towers, and a finite set as its
  subsets. merc classifies function sorts as not enumerable until the rewriter supports
  β-reduction.
- **Native `sum` exploration.** Successor generation for an LPS still calls
  mCRL2's enumerator through the FFI. Replacing it with `enumerate` needs a
  bound on `sum` enumeration that reports truncation instead of hiding it.
