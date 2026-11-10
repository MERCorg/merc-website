```math_preamble
\usepackage[paperwidth=40cm,paperheight=60cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
\newcommand{\hd}{\mathsf{hd}}
\newcommand{\pos}{\mathsf{pos}}
\newcommand{\sub}{\mathsf{sub}}
\newcommand{\reduce}{\mathsf{reduce}}
\newcommand{\deriv}{\mathsf{deriv}}
\newcommand{\lift}{\mathsf{lift}}
\newcommand{\gcp}{\mathsf{gcp}}
\newcommand{\eval}{\mathsf{eval}}
\newcommand{\Pos}{\mathbb{P}}
\newcommand{\F}{\mathbb{F}}
\newcommand{\T}{\mathbb{T}}
\newcommand{\Dom}{\mathcal{D}}
\newcommand{\Lpat}{\mathcal{L}}
\newcommand{\MO}{\mathit{MO}}
\newcommand{\MA}{\mathit{MA}}
```
# The set automaton

A *set automaton* finds every match of every left-hand side of a rewrite
system ([Conditional rewriting, Definition 1](conditional-rewriting.md#def-conditional-rewrite-system)) in a term, inspecting each function symbol of the term
exactly once. This page defines the set automaton and its construction, after

> [EG21] Erkens, R., Groote, J.F. (2021). *A Set Automaton to Locate All Pattern
> Matches in a Term*. In: Theoretical Aspects of Computing – ICTAC 2021,
> LNCS 12819, pp. 67–85. [DOI](https://doi.org/10.1007/978-3-030-85315-0_5)

(Definitions 1 to 8, Theorems 1 to 3), and then how merc's
[`SetAutomaton`](https://mercorg.github.io/merc/merc_sabre/struct.SetAutomaton.html)
deviates from it (Definition 9, Conjecture 1). The automaton is the matching
step of
[`SabreRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.SabreRewriter.html),
the **S**et **A**utomaton **B**ased **R**ewrit**e** engine of
[`merc_sabre`](https://mercorg.github.io/merc/merc_sabre/index.html). It
assumes [Terms, Definitions 1 and 2](../terms/aterms.md#def-term) and
[Conditional rewriting, Definitions 1 to 3](conditional-rewriting.md#def-conditional-rewrite-system).

## Positions and patterns

<a id="def-position"></a>**Definition 1 (position).** A *position* is a finite sequence of positive
natural numbers; $\Pos$ is the set of positions, $\varepsilon$ the empty
sequence (the *root*), and $p.q$ concatenation. Position $p$ is *below* $q$,
$p \le q$, if $p = q.q'$ for some $q'$. With this order $(\Pos, \le)$ is a
join-semilattice, and the join $\gcp(P)$ of a finite non-empty set $P$ is its
*greatest common prefix*. Positions $p$ and $q$ are *comparable* if $p \le q$ or
$q \le p$: $2.2.3$ and $2$ are, $2.2.3$ and $1$ are not, and $\varepsilon$ is
comparable to every position. For a term $t$, $\Dom(t)$ is the set of positions
of $t$, $t[p]$ the subterm at $p \in \Dom(t)$, and $\hd(t)$ its head symbol
([EG21], Section 2 and Definition 1).

<a id="def-pattern-match"></a>**Definition 2 (pattern, match).** Over a signature $\F$ with one variable
$\omega$, a *pattern* is a term in $\T(\F) \setminus \{\omega\}$, and a *pattern
set* $\Lpat$ is a finite non-empty set of patterns. A pattern $\ell$ *matches*
a term $t$ at position $p$ if $\hd(t[p.p']) = \hd(\ell[p'])$ for every
$p' \in \Dom(\ell)$ with $\ell[p'] \neq \omega$. The *subpatterns* of $\ell$
are $\sub(\ell) = \{\ell[p] \mid p \in \Dom(\ell),\ \ell[p] \neq \omega\}$,
extended pointwise to $\sub(\Lpat)$ ([EG21], Section 2).

The patterns of a rewrite system are its left-hand sides with every variable
replaced by $\omega$. A match of a pattern is therefore a match of the rule only
if the rule is left-linear; for a non-linear left-hand side, or a rule with
conditions, Sabre checks the equal variables and the conditions after the
automaton announces the match (see [`matching`](https://mercorg.github.io/merc/merc_sabre/matching/index.html)
and [Condition caching](condition-caching.md)).
[`is_supported_rule`](https://mercorg.github.io/merc/merc_sabre/fn.is_supported_rule.html)
excludes higher-order rules, rules with binders or where clauses, and rules with
variables that do not occur in their left-hand side.

## Set automata

<a id="def-match-goal"></a>**Definition 3 (match goal).** The *match obligations* and *match announcements*
are

```math
\[
\MO = \mathcal{P}(\sub(\Lpat) \times \Pos) \setminus \{\emptyset\}
\qquad
\MA = \Lpat \times \Pos .
\]
```

A *match goal* is a pair in $\MO \times \MA$, written
$\ell_1@p_1, \dots, \ell_n@p_n \to \ell@p$: to announce that $\ell$ matches at
$p$, the subpattern $\ell_i$ must still be observed at $p_i$ for every $i$. Its
positions are $\pos(mo) = \{p \mid (\ell', p) \in mo\}$. A goal
$\ell@p \to \ell@p$ is *fresh*, and a goal $mo \to \ell@\varepsilon$ is a
*root goal* ([EG21], Section 4).

<a id="def-set-automaton"></a>**Definition 4 (set automaton).** A *set automaton* for $\Lpat$ is a tuple
$(S, s_0, L, \delta, \eta)$ of a finite set of states
$S \subseteq \mathcal{P}(\MO \times \MA) \setminus \{\emptyset\}$, an initial
state $s_0 \in S$, a *label* $L : S \to \Pos$, a transition function
$\delta : S \times \F \to \mathcal{P}(S \times \Pos)$ and an output function
$\eta : S \times \F \to \mathcal{P}(\Lpat \times \Pos)$. The empty set is the
final state, with no transitions and no output ([EG21], Section 4).

A state is evaluated at a position $p$ of the term, the pair $(s, p)$ being a
*configuration*: it inspects the head symbol at $p.L(s)$, announces the outputs
of the transition relative to $p$, and continues in every configuration the
transition leads to. These configurations are independent, so they may be
explored in any order, or in parallel.

<a id="def-evaluation"></a>**Definition 5 (evaluation).** For a closed term $t$, the evaluation of $M$ in
configuration $(s, p)$ is

```math
\[
\eval_M(s, p, t) = \{\ell@p.q \mid \ell@q \in \eta(s, f)\}
  \cup \bigcup_{(s', p') \in \delta(s, f)} \eval_M(s', p.p', t)
\quad\text{where } f = \hd(t[p.L(s)]),
\]
```

and the matches of $M$ in $t$ are $\eval_M(s_0, \varepsilon, t)$ ([EG21],
Section 6).

```math algorithm
\begin{algorithmic}[1]
\Function{Match}{$M, t$}
  \State $W \gets \{(s_0, \varepsilon)\}$, $A \gets \emptyset$
  \While{$W \neq \emptyset$}
    \State take a configuration $(s, p)$ out of $W$ \Comment{any order}
    \State $f \gets \hd(t[p.L(s)])$
    \State $A \gets A \cup \{\ell@p.q \mid \ell@q \in \eta(s, f)\}$
    \State $W \gets W \cup \{(s', p.p') \mid (s', p') \in \delta(s, f)\}$
  \EndWhile
  \State \Return $A$
\EndFunction
\end{algorithmic}
```

## Construction

The states are sets of match goals, and the transitions are computed from a
derivative of a state with respect to the symbol observed at its label, much
like Brzozowski derivatives of regular expressions.

<a id="def-derivative"></a>**Definition 6 (derivative).** Observing $f$ at position $p$ changes a match
obligation into

```math
\[
\reduce(mo, f, p) = \{\ell@q \in mo \mid q \neq p\}
  \cup \{\ell[i]@p.i \mid \ell@p \in mo,\ 1 \le i \le \#f,\ \ell[i] \neq \omega\}.
\]
```

The *$f$-derivative* of a state $s$ is
$\deriv(s, f) = \mathit{unchanged} \cup \mathit{reduced} \cup \mathit{fresh}$,
where

```math
\[
\begin{aligned}
\mathit{unchanged} &= \{mo \to ma \in s \mid L(s) \notin \pos(mo)\} \\
\mathit{reduced} &= \{\reduce(mo, f, L(s)) \to ma \mid mo \to ma \in s,\
  \exists \ell\colon \ell@L(s) \in mo \land \hd(\ell) = f,\
  \reduce(mo, f, L(s)) \neq \emptyset\} \\
\mathit{fresh} &= \{\ell@L(s).i \to \ell@L(s).i \mid \ell \in \Lpat,\ 1 \le i \le \#f\}
\end{aligned}
\]
```

([EG21], Section 4.2). A goal with an obligation at $L(s)$ whose head is not
$f$ is *discarded*: it occurs in none of the three sets. A goal whose only
obligation is $f(\omega, \dots, \omega)@L(s)$ is *completed*: its obligation
reduces to $\emptyset$ and its announcement becomes an output.

<a id="def-dependency"></a>**Definition 7 (dependency).** On a finite set $X \subseteq \MO$, obligations
are *directly dependent*, $mo_1 \mathrel{R} mo_2$, if
$\pos(mo_1) \cap \pos(mo_2) \neq \emptyset$, and *dependent*,
$mo_1 \sim_X mo_2$, if they are related by the transitive closure of $R$. This
extends to goals through their obligations, and $[\deriv(s, f)]_\sim$ is the set
of equivalence classes $K$ of the derivative ([EG21], Section 4.3).

<a id="def-set-automaton-of-a-pattern-set"></a>**Definition 8 (set automaton of a pattern set).** For a set of goals $K$, let
$\gcp(K)$ be the greatest common prefix of its announcement positions, and
$\lift(K)$ the goals of $K$ with that prefix removed from every position:
$\lift(K) = \{(\lift(mo), \ell@p') \mid (mo, \ell@\gcp(K).p') \in K\}$ with
$\lift(mo) = \{\ell@p' \mid \ell@\gcp(K).p' \in mo\}$. The set automaton of
$\Lpat$ is given by

```math
\[
\begin{aligned}
s_0 &= \{\ell@\varepsilon \to \ell@\varepsilon \mid \ell \in \Lpat\},
  \qquad L(s_0) = \varepsilon \\
\delta(s, f) &= \{(\lift(K), \gcp(K)) \mid K \in [\deriv(s, f)]_\sim\} \\
\eta(s, f) &= \{ma \mid f(\omega, \dots, \omega)@L(s) \to ma \in s\}
\end{aligned}
\]
```

where $L(s)$ is any position in $\pos(mo)$ of a root goal $mo \to \ell@\varepsilon$
of $s$, fixed when $s$ is created ([EG21], Section 4.7).

Partitioning lets independent parts of the term be explored by independent
configurations, and lifting keeps positions short; together they make the set
of reachable states finite. The construction is a worklist over the states
discovered so far:

```math algorithm
\begin{algorithmic}[1]
\Function{Construct}{$\Lpat$}
  \State $s_0 \gets \{\ell@\varepsilon \to \ell@\varepsilon \mid \ell \in \Lpat\}$, $L(s_0) \gets \varepsilon$
  \State $S \gets \{s_0\}$, $Q \gets [s_0]$ \Comment{a queue}
  \While{$Q \neq []$}
    \State $s \gets \Call{PopFront}{Q}$
    \ForAll{$f \in \F$}
      \State $\eta(s, f) \gets \{ma \mid f(\omega, \dots, \omega)@L(s) \to ma \in s\}$
      \State $\delta(s, f) \gets \emptyset$
      \ForAll{$K \in [\deriv(s, f)]_\sim$}
        \State $s' \gets \lift(K)$
        \If{$s' \notin S$}
          \State $L(s') \gets$ a position of a root goal of $s'$
          \State $S \gets S \cup \{s'\}$, \Call{PushBack}{$Q$, $s'$}
        \EndIf
        \State $\delta(s, f) \gets \delta(s, f) \cup \{(s', \gcp(K))\}$
      \EndFor
    \EndFor
  \EndWhile
  \State \Return $(S, s_0, L, \delta, \eta)$
\EndFunction
\end{algorithmic}
```

## Finiteness and correctness

<a id="thm-finite-automaton"></a>**Theorem 1 (finite automaton).** Every reachable state has a root goal, so its
label is defined, and there are finitely many reachable states; hence
Construct terminates ([EG21], Corollaries 1 and 2).

<a id="thm-one-inspection-per-symbol"></a>**Theorem 2 (one inspection per symbol).** For every closed term $t$, the
configurations reached by evaluating $M$ on $t$ form a finite tree, and
$(s, p) \mapsto p.L(s)$ is a bijection from them to $\Dom(t)$ ([EG21],
Corollaries 3 and 4). Every position of $t$ is inspected exactly once, also
when the configurations are explored in parallel.

<a id="thm-correctness"></a>**Theorem 3 (correctness).** For every closed term $t$,
$\eval_M(s_0, \varepsilon, t) = \{\ell@p \in \Lpat \times \Dom(t) \mid \ell \text{ matches } t \text{ at } p\}$
([EG21], Theorem 1).

Theorems 1 to 3 are proved on paper in [EG21], with proof sketches there and the
details in the technical report it cites; they are not formalised in Lean.
[EG21] (Section 7) also states that evaluation takes $O(d(n + m))$ time, for
$n$ symbols in $t$, $m$ matches and $d$ the maximal depth of a pattern, since
reading the symbol at $p.L(s)$ takes $|L(s)|$ steps, and that the number of
states is exponential in the worst case but at most the number of patterns for
most of the mCRL2 data types it measures.

## The construction in merc {#construction-in-merc}

[`SetAutomaton::new`](https://mercorg.github.io/merc/merc_sabre/struct.SetAutomaton.html#method.new)
follows Construct with the symbols of the rules, the machine-word operations
that the specification evaluates natively, and one stand-in symbol under which every
machine number is matched (see [Machine numbers](../data/machine-numbers.md)). It
differs from Definition 8 in how a derivative is partitioned and in the choice
of labels.

<a id="def-partition-in-merc"></a>**Definition 9 (partition in merc).** For a state $s$ and symbol $f$, merc
partitions the goals of $\mathit{unchanged} \cup \mathit{reduced}$ into the
classes of the transitive closure of *comparability of their announcement
positions*; since $\varepsilon$ is comparable to every position, the goals form
a single class as soon as one of them is a root goal. Each class $K$ is lifted
by $\gcp(K)$ as in Definition 8. Then, for each argument $1 \le i \le \#f$, the
fresh goals at $q = L(s).i$ join the first class with an obligation position
comparable to $q$, lifted by the prefix of that class; if there is none, the
transition gets the destination $(s_0, q)$.

```math algorithm
\begin{algorithmic}[1]
\Function{Destinations}{$s, f$}
  \State $G \gets \mathit{unchanged} \cup \mathit{reduced}$ \Comment{Definition 11, without $\mathit{fresh}$}
  \State $K_1, \dots, K_n \gets$ the classes of $G$ under comparable announcement positions
  \State $D \gets [(\lift(K_1), \gcp(K_1)), \dots, (\lift(K_n), \gcp(K_n))]$
  \For{$i \gets 1, \dots, \#f$}
    \State $q \gets L(s).i$
    \If{some $K_j$ has an obligation position comparable to $q$, $j$ least}
      \State add $\{\ell@q' \to \ell@q' \mid \ell \in \Lpat\}$ to $\lift(K_j)$ in $D$, where $q = \gcp(K_j).q'$
    \Else
      \State append $(s_0, q)$ to $D$
    \EndIf
  \EndFor
  \State \Return $D$, sorted by position
\EndFunction
\end{algorithmic}
```

The fresh goals are grouped as in Definition 7: a fresh goal shares an
obligation position only with a goal whose obligation is at $L(s).i$ itself. The
remaining goals are grouped more coarsely. Two goals that share an obligation
position have comparable announcement positions, since both are prefixes of it
([EG21], Proposition 2), so every class of Definition 7 lies within one class
of Definition 9, but goals with comparable announcement positions need not
share an obligation.

The label of a new state is the lexicographically least obligation position
among its root goals. When these positions are pairwise incomparable, as they
are in the construction of [EG21] (Proposition 2), this is the leftmost one. [EG21] (Section 7)
observes that this choice affects the size of the automaton: for the patterns
$t_{n+1} = f(t_n, g(\omega))$ the leftmost choice gives $n^2 + n$ states and the
rightmost $2n$.

A match announcement in merc also records how many symbols the goal has
observed, which Sabre uses to find the configuration at which the matched
pattern begins. It is part of a goal's identity, so two goals that differ only
in this count give different states.

<a id="conj-construction-in-merc"></a>**Conjecture 1 (construction in merc).** Theorems 1 to 3 hold for the automaton
that SetAutomaton::new constructs with Definition 9 in place of Definition 7.

This is open: the proofs of [EG21] are for the partition of Definition 7 and
have not been redone for Definition 9. The construction does terminate for the
machine-word encoding, for which the alternative below does not.

With `apma` set, SetAutomaton::new builds an *adaptive pattern matching
automaton* instead: every transition has one destination at $\varepsilon$ with
all remaining goals and no fresh goals, so it finds matches at the root only.
[`InnermostRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.InnermostRewriter.html)
and [`NaiveRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.NaiveRewriter.html)
use that variant.

### Why fresh goals are compared with obligations {#why-obligation-positions}

Definition 9 decides whether a fresh position joins a class by the class's
*obligation* positions. The alternative, testing it against the class's
*announcement* positions, does not terminate: a class with a root goal announces
at $\varepsilon$, which is comparable to every position, so it absorbs every
fresh subtree and a fresh copy of every rule. The resulting state never equals
one already built, and the worklist never drains. Obligations reaching this
test are never empty, since a goal without obligations is completed
(Definition 6), so $\varepsilon$ appears among obligation positions only while
a pattern is still anchored at the root.

#### Example: `+` on machine-word `Pos` {#example-on-machine-word-pos}

The machine-word encoding ([Machine numbers, Definition 2](../data/machine-numbers.md#def-machine-word-encoding)) gives `Pos` addition six equations:

```
(@most_significant_digit(w1) + @most_significant_digit(w2)) = ...;
(@concat_digit(p1,w1)        + @most_significant_digit(w2)) = ...;
(@most_significant_digit(w1) + @concat_digit(p2,w2))        = ...;
(@concat_digit(p1,w1)        + @concat_digit(p2,w2))        = ...;
(@succ_pos(p1) + p2) = @succ_pos((p1 + p2));
(p1 + @succ_pos(p2)) = @succ_pos((p1 + p2));
```

The constructors of `Pos` in this encoding are `@c1` and `@succ_pos`, and the
digit functions are mappings, so a term built with successors can still reach
`+`; the last two equations handle it. Each constrains one argument and leaves
the other a variable. After observing `+` at the root, the goals are:

| equation | obligation at position 1 | obligation at position 2 |
|---|---|---|
| digit + digit | `@most_significant_digit(w1)` | `@most_significant_digit(w2)` |
| chain + digit | `@concat_digit(p1,w1)` | `@most_significant_digit(w2)` |
| digit + chain | `@most_significant_digit(w1)` | `@concat_digit(p2,w2)` |
| chain + chain | `@concat_digit(p1,w1)` | `@concat_digit(p2,w2)` |
| succ + * | `@succ_pos(p1)` | *(none)* |
| * + succ | *(none)* | `@succ_pos(p2)` |

All six announce at $\varepsilon$. A goal such as "* + succ" stays a root goal
while only its position-2 obligation is open, so its class keeps announcing at
$\varepsilon$, and with the announcement test the next fresh subtree, from
whichever rule, joins it. Every arithmetic and comparison operator on `Pos` and
`Nat` in this encoding has such a pair of successor equations, so some class
stays open at the root and the construction does not terminate. The binary
encoding ([Machine numbers, Definition 1](../data/machine-numbers.md#def-binary-encoding)) has no second representation of the same values, so
its root goals are told apart after a few observations and the construction
terminates with either test.

### Order of exploration

Sabre explores the destinations of a transition depth first, in sorted position
order: it follows the first and keeps the others as a side branch, which
determines which redex it finds, and rewrites, first. A state's label is chosen
among its root goals, and a class's prefix sorts before a position that was
split off from it, so the root is matched before a split-off subterm is
visited. Compared with the announcement test, a split-off subterm is visited
only after the whole branch of its class; for the rule `f(y, g(x)) = x` applied
to `f(t1, h(...))`, where `h(...)` rewrites to a `g`-term, this explores the
second argument before `t1`, which the rule discards. Whether the order is
measurably less lazy in other cases has not been determined.
