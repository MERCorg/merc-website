```math_preamble
\usepackage[paperwidth=40cm,paperheight=60cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
\newcommand{\nf}{\mathsf{nf}}
\newcommand{\red}{\mathsf{reduce}}
\newcommand{\hd}{\mathsf{hd}}
\newcommand{\var}{\mathsf{var}}
\newcommand{\push}{\mathsf{push}}
\newcommand{\apply}{\mathsf{apply}}
\newcommand{\binder}{\mathsf{binder}}
\newcommand{\rw}{\mathsf{rewrite}}
\newcommand{\construct}{\mathsf{construct}}
\newcommand{\evaluate}{\mathsf{evaluate}}
\newcommand{\ret}{\mathsf{return}}
\newcommand{\prog}{\mathsf{prog}}
```
# Innermost rewriting

An *innermost* rewriter normalises the arguments of a term before it rewrites
the term itself. This page defines the innermost normal form that
[`InnermostRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.InnermostRewriter.html)
of [`merc_sabre`](https://mercorg.github.io/merc/merc_sabre/index.html)
computes (Definition 1), right-hand sides compiled to programs (Definition 2),
and the stack machine that runs them (Definition 3), followed by how a redex is
matched on that stack without being constructed. It assumes
[Conditional rewriting, Definitions 1 and 2](conditional-rewriting.md#def-conditional-rewrite-system)
and [The set automaton, Definitions 1 to 5](set-automaton.md#def-position),
with the automaton built to match at the root only
([The construction in merc](set-automaton.md#construction-in-merc)).

## Innermost normal forms

The rules of a symbol are tried in a fixed order: the order in which the
automaton announces them. A *native* symbol is a machine-word operation that is
[evaluated natively](../data/machine-numbers.md#machine-word-encoding), and
$\mathit{native}(f)(u_1, \dots, u_n)$ is its value, when it is defined.

<a id="def-innermost-normal-form"></a>**Definition 1 (innermost normal form).** For a substitution $\sigma$
that maps every variable to a normal form, the *innermost normal form*
$\nf_\sigma$ of a term and the result $\red(f, u_1, \dots, u_n)$ of a redex whose
arguments $u_i$ are normal forms are

```math
\[
\begin{aligned}
\nf_\sigma(x) &= \sigma(x) && \text{for a variable } x \text{ in the domain of } \sigma \text{, and } x \text{ otherwise} \\
\nf_\sigma(c) &= c && \text{for a machine number } c \\
\nf_\sigma(f(t_1, \dots, t_n)) &= \red(f, \nf_\sigma(t_1), \dots, \nf_\sigma(t_n)) \\[1ex]
\red(f, u_1, \dots, u_n) &= \mathit{native}(f)(u_1, \dots, u_n) && \text{if } f \text{ is native and its value is defined} \\
  &= \nf_\tau(r) && \text{for the first rule } l = r \text{ with } l\tau = f(u_1, \dots, u_n) \text{ whose conditions hold under } \tau \\
  &= f(u_1, \dots, u_n) && \text{otherwise.}
\end{aligned}
\]
```

A condition $u \to v$ holds under $\tau$ if $\nf(u\tau)$ and $\nf(v\tau)$ are
equal; merc also allows conditions that hold if they differ. Since the values
of $\tau$ are normal forms, $\nf_\tau(r)$ does not rewrite them again: it only
rewrites the redexes that $r$ itself builds. The arguments are normalised from
left to right. A binder is normalised as
[Quantifiers in the rewriter](../data/quantifiers.md) describes, also when a
right-hand side contains it
([Binders in right-hand sides](../data/quantifiers.md#binders-in-right-hand-sides)).

Definition 1 is a function only for a terminating system. The innermost order
also makes a system loop that terminates under another order, such as the
recursions in both branches of an `if` that
[Just-in-time rewriting](jitty.md#why-the-innermost-order-is-not-enough)
describes.

## Programs

A right-hand side is instantiated many times, so its structure is compiled
once, when the automaton is built.

<a id="def-program"></a>**Definition 2 (program).** The *program* $\prog_l(r)$ of a right-hand side
$r$ of a rule with left-hand side $l$ is the sequence of instructions

```math
\[
\begin{aligned}
\prog_l(x) &= \var(p) && \text{where } p \text{ is a position of } x \text{ in } l \\
\prog_l(c) &= \push(c) && \text{for a machine number } c \\
\prog_l(f(r_1, \dots, r_n)) &= \prog_l(r_1) \cdots \prog_l(r_n)\ \apply(f, n) \\
\prog_l(\beta) &= \prog_l(x_1) \cdots \prog_l(x_k)\ \binder(\lambda x_1, \dots, x_k.\, \beta, k) && \text{for a binder } \beta \text{ with free variables } x_1, \dots, x_k .
\end{aligned}
\]
```

Running a program pushes the value of every subterm onto a stack: $\var(p)$
the subterm at position $p$ of the matched term, $\push(c)$ the constant, and
$\apply(f, n)$ and $\binder(\beta, k)$ replace the $n$ or $k$ values on top by
one. The program is the term in post-order, so the arguments of a symbol are
the values on top when the symbol is reached. The right-hand side of
`f(x, y) = g(h(x), y)` is the program $\var(1)\ \apply(h, 1)\ \var(2)\ \apply(g, 2)$.

In merc a program is a
[`TermStack`](https://mercorg.github.io/merc/merc_sabre/utilities/struct.TermStack.html)
of [`Instruction`](https://mercorg.github.io/merc/merc_sabre/utilities/enum.Instruction.html)s,
which also instantiates the sides of conditions.

## The rewriting machine

The machine is not recursive: a stack of configurations says what to do with a
stack of values, so that a deep term or a long chain of rule applications does
not use the system stack. Only conditions and binders are normalised by a
nested run of the machine, on the same two stacks.

<a id="def-rewriting-machine"></a>**Definition 3 (rewriting machine).** A *configuration* is one of

- $\rw(t)$: push $\nf_\sigma(t)$;
- $\construct(f, n)$: replace the $n$ values on top by $\red(f, u_1, \dots, u_n)$, for those values $u_1, \dots, u_n$;
- $\evaluate(P, \mathit{pc}, b)$: run the program $P$ from instruction $\mathit{pc}$, with the values from index $b$ on as the arguments of the matched term, and replace those by its value;
- $\ret$: pop the normal form of the term being rewritten.

A *state* is a pair of a stack of configurations and a stack of values.

Every configuration takes its inputs from the top of the value stack and
leaves its result there. The values are therefore normal forms, apart from the
arguments below a running program, and none is tagged as one.

```math algorithm
\begin{algorithmic}[1]
\Function{Normalise}{$t, \sigma$}
  \State push $\ret$ and then $\rw(t)$ onto $C$
  \Loop
    \If{the top of $C$ is $\construct(f, n)$}
      \State pop $\construct(f, n)$ from $C$, and \Call{Reduce}{$f, n$}
    \ElsIf{the top of $C$ is $\evaluate(P, \mathit{pc}, b)$}
      \State \Call{Run}{$P, \mathit{pc}, b$}
    \ElsIf{the top of $C$ is $\rw(t')$}
      \State pop it
      \If{$t' = f(t_1, \dots, t_n)$}
        \State push $\construct(f, n)$, $\rw(t_n)$, \dots, $\rw(t_1)$ onto $C$
        \Statex \Comment{$t_1$ is on top, so the arguments are normalised from left to right}
      \ElsIf{$t'$ is a binder}
        \State push its normal form onto $V$ \Comment{see Quantifiers in the rewriter}
      \Else
        \State push $\nf_\sigma(t')$ onto $V$ \Comment{a variable, or a machine number}
      \EndIf
    \Else
      \State pop $\ret$ from $C$, and \Return the value popped from $V$
    \EndIf
  \EndLoop
\EndFunction
\Statex
\Procedure{Run}{$P, \mathit{pc}, b$}
  \While{$\mathit{pc} < |P|$}
    \State $\mathit{pc} \gets \mathit{pc} + 1$ \Comment{in the configuration on top of $C$}
    \If{$P_{\mathit{pc}} = \var(p)$}
      \State push the subterm at $p$ of the arguments $V_b, V_{b+1}, \dots$ onto $V$
    \ElsIf{$P_{\mathit{pc}} = \push(c)$}
      \State push $c$ onto $V$
    \ElsIf{$P_{\mathit{pc}} = \apply(f, n)$}
      \State \Call{Reduce}{$f, n$}, and \Return \Comment{continues at $\mathit{pc}$ later}
    \Else
      \State normalise the binder of $P_{\mathit{pc}}$ for the values on top, and \Return
    \EndIf
  \EndWhile
  \State pop the configuration from $C$, pop the value $v$ from $V$
  \State remove $V_b, V_{b+1}, \dots$ and push $v$ onto $V$
\EndProcedure
\Statex
\Procedure{Reduce}{$f, n$}
  \State $u_1, \dots, u_n \gets$ the $n$ values on top of $V$
  \If{\Call{Match}{$f, u_1, \dots, u_n$} is the native value $v$}
    \State replace $u_1, \dots, u_n$ by $v$
  \ElsIf{it is a rule $l = r$}
    \State push $\evaluate(\prog_l(r), 0, |V| - n)$ onto $C$ \Comment{its value replaces $u_1, \dots, u_n$}
  \Else
    \State replace $u_1, \dots, u_n$ by $f(u_1, \dots, u_n)$
  \EndIf
\EndProcedure
\end{algorithmic}
```

A program runs in place: its configuration keeps the program counter, and
reaching a symbol suspends it until the redex of that symbol is normalised on
top. A rule application therefore costs one configuration, and every
instruction is read once. The right-hand side of a rule that applies runs on
top of the arguments it was matched with, which are removed when it is done.

The alternative is to place the configurations of a whole right-hand side on
the stack when a rule applies: one per symbol, each with the index of the slot
that its result fills, and the slots reserved in advance. That copies every
right-hand side for every application, and makes the layout of the stack
depend on the shape of the term.

## Matching without building the redex

A redex is matched where it lies: its head symbol $f$ applied to the values on
top. The automaton walks these values without constructing $f(u_1, \dots, u_n)$,
since its path only depends on the symbols that it inspects, and the
variables of a right-hand side take their values from the same arguments. A
term is only built when no rule applies, as the normal form. Constructing every
redex and discarding it again makes the innermost rewriter
[considerably slower](../../benchmarks/rewriting.md#matching-without-building-the-redex).

The automaton matches at the root only, so every transition has one
destination and the walk is a single path of states. Along it, the
announcements of the transitions are the candidate rules in the order in which
Definition 1 tries them.

```math algorithm
\begin{algorithmic}[1]
\Function{Match}{$f, u_1, \dots, u_n$}
  \State $t \gets f(u_1, \dots, u_n)$ \Comment{read from the stack, never built}
  \State $s \gets s_0$
  \Loop
    \State $g \gets \hd(t[L(s)])$; \Return no match if $t[L(s)]$ is a variable
    \If{$s = s_0$ and $g$ is native}
      \State \Return $\mathit{native}(g)(u_1, \dots, u_n)$, or no match if it is undefined
    \EndIf
    \For{every rule $l = r$ announced by $\eta(s, g)$, in order}
      \If{the positions of equal variables of $l$ hold equal subterms of $t$}
        \If{the conditions of the rule hold under the match $\tau$}
          \State \Return the rule
        \EndIf
      \EndIf
    \EndFor
    \State \Return no match if $\delta(s, g)$ is empty
    \State $s \gets$ the state of the destination of $\delta(s, g)$
  \EndLoop
\EndFunction
\end{algorithmic}
```

Checking a condition normalises its sides on the same stacks, whereas the
walk reads the arguments from the value stack. In merc the walk therefore
stops at a rule with conditions, the conditions are checked after it, and the
walk continues just after that rule if they do not hold. It stops at most once
per candidate rule with conditions and needs no memory for the candidates, and
the rules are still tried in the order of Definition 1. The sides of a
condition are instantiated from the arguments, as a right-hand side is, and
their normal forms are cached ([Condition caching](condition-caching.md)).
