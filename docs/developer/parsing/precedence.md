# Precedence

This page compares how merc and mCRL2 group data expressions that mix prefix and
infix operators, defines the grouping merc's parser produces (Definition 4,
Theorem 3), and relates the case where the two differ to the literature on
operator-precedence conflicts.

merc and mCRL2 implement the same documented `DataExpr` precedence table.
In particular, quantifiers and lambdas have low precedence, while operators
such as negation, unary minus, and cardinality have high precedence. They
usually therefore assign the same grouping to ordinary expressions.

- merc first recognizes an expression as a sequence of operands and
  operators, then applies a Pratt parser to build the precedence tree. Each
  prefix operator parses its operand according to that operator's own
  binding power.
- mCRL2 uses a grammar parser with precedence and associativity annotations
  on productions. It can consider multiple valid parse trees and select one
  using those annotations.

For example, both parse `exists d: Bool . d && q` as `exists d: Bool. (d &&
q)`: the low-precedence quantifier is the outermost expression, and its body
includes the conjunction. The difference discussed below appears only in
more deeply nested combinations of prefix and infix operators.

## Divergence

They disagree the moment a tighter-binding prefix operator (`!`) is placed
directly in front of a looser-binding one (`exists`/`forall`), with an
infix operator following the quantifier's body:

```
!exists d: D . X && Y
```

merc parses this as `!(exists d: D . (X && Y))` — negation wrapping the whole
existential, `&&` inside its scope. mCRL2's actual parser parses it as
`(!exists d: D . X) && Y` — negation truncated to just the bare existential,
`&&` outside both it and the negation. This isn't a cosmetic
pretty-printing difference: the two readings bind `X`/`Y` (and any variables
they share with `d`) under genuinely different scopes, so a specification
that relies on the implicit grouping means something different — or fails to
type check — depending on which tool reads it.

### merc's Pratt parser

merc's parser uses pest's `PrattParser`, a standard operator-precedence-climbing
algorithm. The precedence *levels* of the data operators are those of the mCRL2
grammar: among others, the quantifiers and `lambda` have level 1, `&&` has
level 4, and `!` and unary minus have level 12.

**Definition 4 (operand of a prefix operator).** In precedence climbing, the
operand of a prefix operator of level $\ell$ is the longest expression that
starts directly after it and contains no infix operator of level at most $\ell$
outside brackets, and outside the operands of nested prefix operators.

**Theorem 3 (nested prefix operators).** If a prefix operator of level $\ell_1$ is
directly followed by a prefix operator of level $\ell_2 < \ell_1$, then the operand
of the inner operator extends over every infix operator of level greater than
$\ell_2$ that follows, regardless of $\ell_1$; the outer operator's operand is the
inner operator applied to that operand.

*Proof idea.* Precedence climbing parses the operand of a prefix operator by one
recursive call, bounded by that operator's own level. The inner call, bounded by
$\ell_2$, consumes every following infix operator of a higher level before it
returns, and the outer call, bounded by $\ell_1$, only receives the result. This
is a property of precedence climbing in general, not of merc.

For `!exists d: D . X && Y` the outer operator is `!` (12), the inner `exists`
(1), and `&&` (4) has a higher level than `exists`, so the result is
`!(exists d: D . (X && Y))`. Without the quantifier, `!X && Y`, the operand of
`!` stops before `&&`, whose level 4 is not above 12, giving `(!X) && Y`. The
quantifier is what changes the outcome, by handing control to its own, much
lower, level partway through.

### mCRL2's reading, verified against the real parser

dparser is a GLR (generalized LR) parser: on genuinely ambiguous input it
builds a shared packed parse forest of every valid derivation and then
disambiguates using the priority/associativity annotations — a different
mechanism from a single bounded recursive descent.

**Observation.** Run against mCRL2's parser, these expressions are grouped as
follows:

| expression | mCRL2 parses it as |
|---|---|
| `exists d: Bool . d && q` | `exists d: Bool. (d && q)` |
| `!exists d: Bool . d && q` | `(!(exists d: Bool. d)) && q` |
| `!exists d: Bool . d \|\| q` | `(!(exists d: Bool. d)) \|\| q` |
| `!exists d: Bool . d => q` | `(!(exists d: Bool. d)) => q` |
| `!exists d: Bool . d == q` | `(!(exists d: Bool. d)) == q` |
| `!!exists d: Bool . d && q` | `(!!(exists d: Bool. d)) && q` |
| `!forall d: Bool . d && q` | `(!(forall d: Bool. d)) && q` |

The pattern is consistent with the following model: for a span with more than
one valid derivation, dparser picks the derivation whose *outermost* connective
has the lowest priority number among the outermost connectives actually
competing for that position — not "each prefix operator bounds its own reach
independently," which is what the Pratt parser does. For the bare `exists d. d
&& q`, the competing roots are `exists` (1) and `&&` (4); `exists` wins (1 < 4)
and swallows the `&&`. For `!exists d. d && q`, the competing roots are `!` (12,
wrapping the maximal exists-through-`&&` reading) and `&&` (4, with a minimal
`!(exists d. d)` as its left operand); `&&` wins (4 < 12), which forces the
`!`/`exists` pair into the smallest shape compatible with that — `d` alone.
`exists`'s own very low priority (1) never enters the comparison, because in the
winning derivation `exists` isn't a candidate root at all; it's nested two
levels down.

## Literature

Parsing-technology research distinguishes two classes of priority/associativity
ambiguity:

- A **shallow conflict** is one a disambiguation filter can resolve by
  looking only at a parse node and its direct children — the ordinary case
  of "which of these two immediately-adjacent operators wins."
- A **deep conflict** needs a pattern check at *unbounded* depth, because a
  low-precedence operator can be shadowed by a higher-precedence one several
  levels down a subtree's left or right edge — exactly the `!`/`exists`/`&&`
  shape here, where the conflict between `exists` (1) and `&&` (4) is
  mediated through an intervening `!` (12) rather than being direct siblings.

This terminology and the underlying analysis come from Eelco Visser's group
at TU Delft: Klint & Visser first formalized declarative disambiguation as
*filters* over parse trees (["Using Filters for the Disambiguation of
Context-free Grammars"](https://homepages.cwi.nl/~paulk/publications/ASMICS94.ps),
1994) — the semantics SDF2 implements, and the same general shape as
dparser's per-production `right N`/`left N`/`binary_op_*` priority and
associativity annotations: declare a priority on each production, then prune
parse-tree patterns that would violate it. 

Afroozeh, van den Brand, Johnstone, Scott & Vinju (["Safe Specification of
Operator Precedence Rules"](https://doi.org/10.1007/978-3-319-02654-1_8), SLE
2013) showed that filters of this kind are provably unable to resolve deep
conflicts: the very case where a low-priority prefix operator (`exists`) is
separated from the higher-priority operator it should or shouldn't absorb (`&&`)
by an intervening node (`!`).

Amorim, Steindorfer & Visser (["Towards Zero-Overhead Disambiguation of Deep
Priority Conflicts"](https://arxiv.org/abs/1803.10215), *The Art, Science,
and Engineering of Programming* 2(3), 2018, article 13) name and classify the
pattern as an **"operator-style conflict"** — their own minimal example is
`if(e) e2 + e3` mixed with an outer `+`, structurally identical to
`!(exists d. body)` mixed with an outer `&&`: a lower-priority prefix
(`if`/`exists`) directly followed by a higher-priority infix (`+`/`&&`). They
state the interpretation everyone actually wants — "the addition to the left
of the conditional expression extends as far as possible," i.e. the
low-priority prefix's body swallows the high-priority infix — is the
supposedly correct one; the other reading, where the prefix's body gets
truncated and the infix escapes outward, is the one every disambiguation
technique they survey is trying to rule out. 

## Resolution

That "correct" reading is
precisely merc's `!(exists d: D . (X && Y))` — and the "wrong" one their
paper is written to rule out is precisely what mCRL2's dparser produces here.
Their own related-work section singles out exactly the mechanism dparser
uses — a flat priority/associativity annotation per production, filtered by
checking only a node's direct parent-child relation, with no grammar
rewriting and no memory of what's structurally nested inside what (this is
the semantics Klint & Visser's filters give SDF2, and it's the same shape as
`mcrl2_syntax.g`'s `right N`/`binary_op_*` annotations) — as provably
unable to solve deep conflicts: "*\[SDF2's filter semantics\] only targets
conflicts by checking a parent-child relation in a tree, \[so\] this solution
is not able to solve deep priority conflicts.*" Getting an operator-style
conflict right instead requires either rewriting the grammar into new
non-terminals that track "what kind of thing can legally sit at this edge"
(the *contextual grammars* technique the 2018 paper builds on, and the
tree-automaton-restricted grammars of Adams & Might, ["Restricting Grammars
with Tree Automata"](https://doi.org/10.1145/3133906), OOPSLA 2017) or a
parser extended with genuine data-dependency to track that context at parse
time — machinery `mcrl2_syntax.g` doesn't have.

Precedence climbing — the family Pratt parsing and merc's `PrattParser`
belong to (traced back to Clarke, *The Top-down Parsing of Expressions*,
1986, and popularized for hand-written parsers by Pratt's 1973 "Top Down
Operator Precedence") — sidesteps the whole conflict class *by construction*,
not by explicitly handling it: a prefix operator's reach is always settled by
one bounded recursive call using its own precedence, so the algorithm never
builds an ambiguous forest that needs filtering afterward in the first place.
That's why merc lands on the literature's "correct" reading without any
special-casing for this shape — it's a parser architecture that the deep/
shallow conflict distinction doesn't apply to, not a grammar that happens to
get this one case right.
