```math_preamble
\usepackage[paperwidth=40cm,paperheight=60cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
\newcommand{\strat}{\mathsf{strat}}
\newcommand{\rw}{\mathsf{rewrite}}
\newcommand{\try}{\mathsf{try}}
\newcommand{\need}{\mathsf{needed}}
```
# Just-in-time rewriting

A *just-in-time* (jitty) rewriter rewrites an argument of a function symbol
only when a rule of that symbol needs it, in an order that a *strategy* per
symbol prescribes, after

> [vdP01] van de Pol, J. (2001). *Just-in-time: on Strategy Annotations*. In:
> International Workshop on Reduction Strategies in Rewriting and Programming
> (WRS 2001), ENTCS 57, pp. 41–63.
> [DOI](https://doi.org/10.1016/S1571-0661(04)00267-1)

This page defines strategies and how merc generates them (Definitions 1 to 4),
jitty normalisation (Definition 5) and its correctness (Theorems 1 and 2), and
then how
[`JittyRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.JittyRewriter.html)
and
[`InnermostRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.InnermostRewriter.html)
of [`merc_sabre`](https://mercorg.github.io/merc/merc_sabre/index.html)
implement it with one stack machine. It assumes
[Conditional rewriting, Definitions 1 and 2](conditional-rewriting.md#def-conditional-rewrite-system)
and [The set automaton, Definition 1](set-automaton.md#def-position).

## Why the innermost order is not enough

An *innermost* rewriter rewrites every argument of a term to normal form
before it tries the rules at the root. The data equations that merc takes over
from mCRL2 are written for a jitty rewriter, which evaluates
`if(c, t, e)` by rewriting `c` first and then only the selected branch.
Innermost rewriting evaluates both branches, so a recursion in one branch is
unfolded even when the other branch is taken:

- Comparison of `Pos` under the [binary encoding](../data/machine-numbers.md#def-binary-encoding)
  is defined by
  `@cDub(b,p) < @cDub(c,q) = if(c => b, p < q, p <= q)`, with a recursive call
  in both branches. Innermost rewriting takes $2v - 2$ steps for `v - 1 < v`,
  linear in the value $v$ rather than in its number of bits.
- Exponentiation under the [machine-word encoding](../data/machine-numbers.md#def-machine-word-encoding)
  is defined by a recursion `@exp_aux3n` whose else branch calls itself with a
  shifted word, which stays `0` once it is `0`. Innermost rewriting does not
  terminate on `exp(3, 5)`.

A strategy fixes this per function symbol, without changing the equations.

## Strategies

Fix a conditional rewrite system and a function symbol $f$ of arity $n$, and
let $R_f$ be its rules whose left-hand side has head $f$ applied to $n$
arguments. Arguments are numbered $1, \dots, n$.

<a id="def-strategy"></a>**Definition 1 (strategy).** A *strategy* for $f$
is a finite sequence of steps, each either $\rw(i)$ for an argument
$1 \le i \le n$, or $\try(R)$ for a set of rules $R \subseteq R_f$, in which no
argument is rewritten twice. The arguments *rewritten before* step $k$ are the
$i$ of the steps $\rw(i)$ among the first $k - 1$ steps.

A model checker needs normal forms, so in merc, as in mCRL2, the arguments
that no step rewrites are rewritten after the last step (Definition 5).

<a id="def-needed-argument"></a>**Definition 2 (needed argument).** Let
$c \to f(l_1, \dots, l_n) = r$ be a rule. Its argument $i$ is *needed* if
$l_i$ is not a variable, or if $l_i$ is a variable $x$ and

1. $x$ occurs more than once in $f(l_1, \dots, l_n)$, or
2. $x$ occurs in the condition $c$, or
3. $x$ occurs more than once in $r$, or
4. $x$ occurs in $r$ inside a [binder](../data/quantifiers.md#def-binder).

$\need(\rho)$ is the set of needed arguments of the rule $\rho$.

The first two conditions are what matching and the condition need to inspect:
a non-variable argument is matched against, a repeated variable compares the
normal forms of its occurrences, and a condition is evaluated on normal forms.
The other two keep the rewriter efficient and simple. A variable copied into
the right-hand side would otherwise be rewritten once per copy, and a binder of
a right-hand side is rewritten under the normal forms of its free variables
([Quantifiers, binders in right-hand sides](../data/quantifiers.md#binders-in-right-hand-sides)).
Conditions 1 to 3 are mCRL2's; condition 4 is merc's.

<a id="def-generated-strategy"></a>**Definition 3 (generated strategy).**
The *generated strategy* for $f$ is the result of the following procedure, in
which the rules of $R_f$ are ordered as in the specification:

```math algorithm
\begin{algorithmic}[1]
\Function{Generate}{$f$}
  \State $P := R_f$; $D := \emptyset$; $s := \varepsilon$
  \While{$P \neq \emptyset$}
    \State $T := \{\rho \in P \mid \need(\rho) \subseteq D\}$
    \If{$T \neq \emptyset$}
      \State $s := s \cdot \try(T)$; $P := P \setminus T$
    \Else
      \Statex \Comment{some rule in $P$ needs an argument outside $D$}
      \State $i :=$ the argument $i \notin D$ with the most rules $\rho \in P$ such that $i \in \need(\rho)$, the lowest on a tie
      \State $s := s \cdot \rw(i)$; $D := D \cup \{i\}$
    \EndIf
  \EndWhile
  \State \Return $s$
\EndFunction
\end{algorithmic}
```

The procedure is that of mCRL2's jitty rewriter. Ties go to the lowest
argument, the order in which the machine rewrites the arguments of an eager
symbol, so that a symbol whose rules need all its arguments is rewritten in the
same order by both rewriters. It tries every rule of $R_f$ exactly once, as
soon as all its needed arguments are rewritten.

For example, the rules `if(true, x, y) = x` and `if(false, x, y) = y` both
need only argument 1, so the strategy of `if` is $\rw(1), \try(\{\text{both
rules}\})$. For the four rules `b && true = b`, `b && false = false`,
`true && b = b` and `false && b = false` the strategy is
$\rw(1), \try(\{\text{the last two}\}), \rw(2), \try(\{\text{the first two}\})$:
a conjunction whose first argument is `false` is `false` without rewriting its
second.

<a id="def-lazy-symbol"></a>**Definition 4 (lazy symbol).** A strategy is
*eager* if its steps up to the first $\try$ step rewrite every argument, and a
symbol is *lazy* if its generated strategy is not eager.

An eager symbol behaves exactly as under innermost rewriting, so merc only
keeps strategies for lazy symbols. A single rule with a variable argument that
it does not need, such as `p < @c1 = false`, makes a symbol lazy.

## Jitty normalisation

<a id="def-jitty-normalisation"></a>**Definition 5 (jitty normalisation).**
Given a strategy $\strat(f)$ for every function symbol $f$, jitty
normalisation is the partial function computed by

```math algorithm
\begin{algorithmic}[1]
\Function{Jitty}{$t$}
  \If{$t$ is a variable or has no strategy}
    \State \Return $t$, or its innermost normal form
  \EndIf
  \State $f(t_1, \dots, t_n) := t$; $D := \emptyset$
  \For{each step of $\strat(f)$, in order}
    \If{the step is $\rw(i)$}
      \State $t_i := \Call{Jitty}{t_i}$; $D := D \cup \{i\}$
    \ElsIf{the step is $\try(R)$, and a rule $c \to l = r$ in $R$ and $\sigma$ have $l\sigma = f(t_1, \dots, t_n)$ and $c\sigma$ holds}
      \State \Return $\Call{Jitty}{r\sigma}$
    \EndIf
  \EndFor
  \For{each argument $i \notin D$}
    \State $t_i := \Call{Jitty}{t_i}$
  \EndFor
  \State \Return $f(t_1, \dots, t_n)$
\EndFunction
\end{algorithmic}
```

where a condition $u \to v$ holds under $\sigma$ if $\Call{Jitty}{u\sigma}$
and $\Call{Jitty}{v\sigma}$ are equal, and a symbol without a strategy is
eager: its arguments are normalised first and then all its rules are tried.

Innermost rewriting is the case in which every symbol is eager. Since a $\try$
step is a rewrite step at the root, and a $\rw(i)$ step rewrites a subterm, the
result is reachable from the input:

<a id="thm-jitty-soundness"></a>**Theorem 1 (soundness).** If
$\Call{Jitty}{t}$ terminates, $t$ rewrites in zero or more steps to
$\Call{Jitty}{t}$, where a rule applies when the two sides of each of its
conditions rewrite to a common term.

The last clause is weaker than
[Conditional rewriting, Definition 2](conditional-rewriting.md#def-rewriting),
which asks $u\sigma$ to rewrite to $v\sigma$; the two agree when $v\sigma$
is a normal form. That is the case for the data equations of a specification,
whose condition $c$ becomes the condition $c \to \mathit{true}$. The innermost
rewriter checks conditions the same way.

<a id="thm-jitty-normal-form"></a>**Theorem 2 (normal forms).** If every
strategy is generated (Definition 3) and $\Call{Jitty}{t}$ terminates, its
result is a normal form.

*Proof idea.* By induction on the recursion, every argument of the result is a
normal form. A rule $\rho$ of $f$ was tried at one step, after its needed
arguments were rewritten; every later step only rewrites arguments outside
$\need(\rho)$, which are variables of $\rho$ that occur once in its left-hand
side and not in its condition. Whether $\rho$ matches, and whether its
condition holds, does not depend on those arguments, so a rule that did not
apply when it was tried does not apply to the result either.

Neither theorem is formalised in Lean; Theorem 2 rests on the proof idea
above. A jitty normalisation can terminate where innermost rewriting does not,
as for `exp` above.

## The implementation in merc

[`JittyRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.JittyRewriter.html)
generates the strategy of every symbol with rules (Definition 3) and keeps those
of the lazy symbols (Definition 4). Three kinds of symbol stay eager regardless:
constants, symbols whose rules apply them to different numbers of arguments
(higher-order application), and the machine-word operations that are
[evaluated natively](../data/machine-numbers.md#machine-word-encoding), which need all
their arguments, as in mCRL2. A lazy symbol applied to another number of
arguments than its rules is eager and has no rules, so it is a normal form once
its arguments are.

### One machine for both rewriters

`JittyRewriter` and
[`InnermostRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.InnermostRewriter.html)
are the same rewriting machine, which differ only in when they rewrite the
arguments of a symbol, so that comparing them measures the strategies and
nothing else. The innermost rewriter rewrites every argument, from left to
right, before the symbol is matched; the jitty rewriter runs the strategy of a
lazy symbol instead.

The machine is not recursive: a stack of configurations says what to do with a
stack of values, and it handles strategy steps, rule applications and
suspended arguments in one loop. Every configuration takes its inputs from the
top of the values and leaves its result there, so the values are normal forms,
except the arguments of a strategy in progress that it has not rewritten yet.
Only conditions and binders rewrite recursively, as in the innermost rewriter.
Tail calls in a branch, such as `upto(n, k) = if(n < k, upto(n + 1, k), n)`,
therefore run in constant system stack, which a loop of $10^6$ iterations
confirms.

The machine is that of [Innermost rewriting](innermost.md#the-rewriting-machine):
right-hand sides are [programs](innermost.md#def-program) that run in place
with a program counter, and a redex is
[matched without being built](innermost.md#matching-without-building-the-redex).
The jitty rewriter adds suspended arguments to it.

The stacks are
[protected containers](../terms/aterms.md#protected-and-borrowed-terms), and every
access to one takes and releases the term pool. The steps that need nothing but the stacks,
which are running programs, matching, applying rules without conditions and
the steps of strategies, are therefore taken in a single access to both. That
postpones garbage collection, so the access is released every 256 steps.
Taking every step in an access of its own makes both rewriters
[noticeably slower](../../benchmarks/rewriting.md#term-pool-access).

Matching uses [set automata](set-automaton.md), each matching at the root
only. The eager symbols share one automaton, from which the rules of lazy
symbols are left out. Each $\try$ step of a lazy symbol has an automaton of
its own, for just the rules it tries.

### Suspended arguments

An argument that the strategy has not rewritten yet is *suspended*. In the
input term it is the raw subterm. In a right-hand side $r\sigma$ it is a
*closure*: a block of the program of $r$ that builds the argument, compiled
after the program itself and only run when the argument is needed, together
with the *environment* of the rule application. The environment holds the
arguments of the matched term, which the variables of the block refer to, so
the term $l\sigma$ itself is never built. A suspended argument of the matched
term stays suspended in the environment: its raw subterm, or its own closure.

For example, `f(b, x) = if(b, g(x), 0)` leaves `x` unrewritten unless the
first branch is taken, as Definition 5 does with $r\sigma$. A variable that a
rule passes on unchanged to a lazy position passes on its suspended value,
rather than a new closure around it, so that a loop does not build a chain of
closures. The REC rule `auxdiv(s(X), s(Y), M) = auxdiv(X, Y, M)`, in which
`auxdiv` does not need `M`, only passes `M` on.

Closures can be passed on into later environments, so how long an environment
lives is only known at run time, and environments are reference counted. They
are kept in one table whose argument slots are reused, so that a rule
application allocates nothing. A suspended argument that no later step and no
right-hand side asks for is never rewritten, and costs nothing but its slot.

## Metrics

Rewrite steps, symbol comparisons, condition cache hits, and the number of
applications of every rule are counted by
[`RewriteMetrics`](https://mercorg.github.io/merc/merc_sabre/struct.RewriteMetrics.html),
which `merc_sabre` only gathers when its `metrics` feature is enabled, since
counting slows down every step. The `merc-rewrite` tool, built with its
`metrics` feature, logs them after every rewrite; its `jitty` rewriter is the
`JittyRewriter`.

## Performance

Under the binary encoding the jitty rewriter removes the exponential cost of
comparisons, which dominates every benchmark that compares numbers under
innermost rewriting. Where both rewriters do the same work, the jitty rewriter
is slower. A lazy
symbol goes through its strategy a step at a time, with a configuration per
step and an automaton per $\try$, where the innermost rewriter matches once
after rewriting all arguments; a right-hand side with lazy symbols moreover
runs in an environment.

[Rewriting benchmarks, Rewriter comparison](../../benchmarks/rewriting.md#rewriter-comparison)
gives the measurements, including the comparison with mCRL2.
