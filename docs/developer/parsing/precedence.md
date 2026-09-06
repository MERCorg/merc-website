# Precedence: Pest (merc) vs. dparser (mCRL2)

!!! Warning
    Rewrite this to show the difference between mCRL2 and merc, and also to explain the deep priority issue in more detail.

`merc_syntax` and mCRL2 both parse the same documented operator-precedence
table for `DataExpr` — the one from the mCRL2 language reference, with
`forall`/`exists`/`lambda` at the loosest level (1) and function
application/negation/unary-minus/`#` at the tightest (12-14, depending on
context). Both grammars encode the *same numbers*:

- merc: [`crates/syntax/mcrl2_grammar.pest`](https://github.com/MERCorg/merc/blob/main/crates/syntax/mcrl2_grammar.pest)
  parses `DataExpr` as a flat, unprioritized token stream —
  `DataExprPrefix* ~ DataExprPrimary ~ DataExprPostfix* ~ (DataExprInfix ~
  DataExprPrefix* ~ DataExprPrimary ~ DataExprPostfix*)*` — and the actual
  precedence lives entirely in a second pass:
  [`crates/syntax/src/precedence.rs`](https://github.com/MERCorg/merc/blob/main/crates/syntax/src/precedence.rs)'s
  `DATAEXPR_PRATT_PARSER`, a `pest::pratt_parser::PrattParser` built with one
  `.op(...)` call per precedence level, lowest first (`forall`/`exists`/
  `lambda`, then `=>`, `||`, `&&`, ... , up to `*`/`.`/`!`/unary `-`/`#`
  sharing the tightest level).
- mCRL2: [`libraries/core/source/mcrl2_syntax.g`](https://github.com/mCRL2org/mCRL2/blob/master/libraries/core/source/mcrl2_syntax.g)
  is the actual grammar dparser compiles (via `make_dparser`, see
  `DPARSER_SOURCES` in `libraries/core/CMakeLists.txt` — this is not a
  documentation-only file). Every alternative in the `DataExpr` production
  carries its own priority as a trailing annotation (dparser writes these
  with a leading dollar-sign sigil), e.g. `'exists' VarsDeclList '.'
  DataExpr` is annotated `right 1` and `'!' DataExpr` is annotated `right
  12`, with the binary operators' priorities set on the operator token
  itself via a `binary_op_left`/`binary_op_right` annotation.

Since the numbers agree, simple chains parse identically. Both give `exists
d: Bool. (d && q)` for a bare `exists d: Bool . d && q` — confirmed by
parsing it with each toolchain directly (`DataExpr::parse` in `merc_syntax`;
`mcrl2::data::parse_data_expression` in mCRL2's `libmcrl2_data`). The
existential is the lowest-precedence operator present, so it becomes the
outermost node and its scope extends through the `&&`, exactly as the table
prescribes.

## Where they diverge: a negated quantifier followed by a lower-precedence operator

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

### merc's reading, traced through the Pratt parser

Pest's `PrattParser::expr` is a standard operator-precedence-climbing
algorithm (`nud`/`led`, see
[`pratt_parser.rs`](https://github.com/pest-parser/pest/blob/master/pest/src/pratt_parser.rs)
in the `pest` crate): a prefix operator's `nud` recurses into its operand
with a right-binding-power of `own_precedence - 1`, and *that recursive call*
is the only thing bounding what the operand consumes.

Tracing `! exists d: D . X && Y` (using merc's actual levels: `!` is 130,
`exists` is 20, `&&` is 50 — see `precedence.rs:123-144`):

1. Top level sees `!` (prec 130) and recurses for its operand with
   `rbp = 129`.
2. That recursion's `nud` immediately sees `exists` (prec 20, *not* 130 —
   each prefix uses its own precedence regardless of what's enclosing it) and
   recurses again for *its* operand with `rbp = 19`.
3. That innermost call parses `X`, then loops: is `19 < prec(&&) = 50`? Yes —
   so it consumes `&& Y` right there, before ever returning to the `exists`
   or `!` frames. The existential's operand is already `X && Y` by the time
   anyone outside it gets a say.
4. Both outer frames just wrap what they were handed: `exists d:D. (X && Y)`,
   then `!(...)`.

The general rule this illustrates: **once a Pratt parser enters a prefix
operator's `nud`, how far that operator's operand extends is governed solely
by its own precedence — an enclosing, tighter-binding prefix cannot claw back
what a nested, looser-binding prefix already consumed.** This is a structural
property of precedence-climbing for chained prefix operators with
non-monotonic precedence (tight-then-loose), not a merc-specific bug, and it
is exactly why `!X && Y` (no quantifier in between) behaves the "expected"
way — there `!`'s own `rbp = 129` is what bounds the operand, `129 <
prec(&&) = 50` is false, so `!` stops right after `X` and `&&` ends up
outside it, giving `(!X) && Y`. The quantifier is what changes the outcome,
by handing control to its own, much lower, precedence partway through.

### mCRL2's reading, verified against the real parser

dparser is a GLR (generalized LR) parser: on genuinely ambiguous input it
builds a shared packed parse forest of every valid derivation and then
disambiguates using the priority/associativity annotations — a different
mechanism from a single bounded recursive descent. We verified the actual
behavior directly against mCRL2's built `libmcrl2_data`/`libmcrl2_core`
(`mcrl2::data::parse_data_expression`, which parses and type-checks in one
step), rather than reasoning from the grammar file alone:

| expression | mCRL2 parses it as |
|---|---|
| `exists d: Bool . d && q` | `exists d: Bool. (d && q)` |
| `!exists d: Bool . d && q` | `(!(exists d: Bool. d)) && q` |
| `!exists d: Bool . d \|\| q` | `(!(exists d: Bool. d)) \|\| q` |
| `!exists d: Bool . d => q` | `(!(exists d: Bool. d)) => q` |
| `!exists d: Bool . d == q` | `(!(exists d: Bool. d)) == q` |
| `!!exists d: Bool . d && q` | `(!!(exists d: Bool. d)) && q` |
| `!forall d: Bool . d && q` | `(!(forall d: Bool. d)) && q` |

The truncation happens purely from `!` sitting directly in front of the
quantifier — it reproduces at any chain depth (`!!`), for `forall` as well as
`exists`, and for every infix operator we tried regardless of how that
operator's own priority compares to `!`'s (`=>` at 2 and `==` at 5 are both
excluded, even though `==` numerically outranks `!` itself). The one thing
that changes the outcome is parentheses: `!(exists d: Bool . d && q)` and
`(!exists d: Bool . d) && q` both parse exactly as written, confirming the
ambiguity is real and both readings are individually valid mCRL2 — dparser
just always resolves the unparenthesized form the second way.

The pattern is consistent with (though we did not trace dparser's C
implementation in `3rd-party/dparser/gram.c` to confirm) the following
model: for a span with more than one valid derivation, dparser picks the
derivation whose *outermost* connective has the lowest priority number among
the outermost connectives actually competing for that position — not "each
prefix operator bounds its own reach independently," which is what the
Pratt parser does. For the bare `exists d. d && q`, the competing roots are
`exists` (1) and `&&` (4); `exists` wins (1 < 4) and swallows the `&&`. For
`!exists d. d && q`, the competing roots are `!` (12, wrapping the maximal
exists-through-`&&` reading) and `&&` (4, with a minimal `!(exists d. d)` as
its left operand); `&&` wins (4 < 12), which forces the `!`/`exists` pair
into the smallest shape compatible with that — `d` alone. `exists`'s own very
low priority (1) never enters the comparison, because in the winning
derivation `exists` isn't a candidate root at all; it's nested two levels
down.

## What the parsing literature says

This isn't a quirk unique to mCRL2's grammar — it's a named, well-studied
phenomenon. Parsing-technology research distinguishes two classes of
priority/associativity ambiguity:

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
parse-tree patterns that would violate it. Aasa (["Precedences in
Specifications and Implementations of Programming
Languages"](https://doi.org/10.1016/0304-3975(95)90680-J),
*Theoretical Computer Science* 142(1), 1995) and later Afroozeh, van den
Brand, Johnstone, Scott & Vinju (["Safe Specification of Operator Precedence
Rules"](https://doi.org/10.1007/978-3-319-02654-1_8), SLE 2013) showed that
filters of this kind — checking only a direct parent-child relationship —
are provably unable to resolve deep conflicts: the very case where a
low-priority prefix operator (`exists`) is separated from the higher-priority
operator it should or shouldn't absorb (`&&`) by an intervening node (`!`).
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
technique they survey is trying to rule out. That "correct" reading is
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

## Which is "more correct"?

Neither grammar is wrong relative to the mCRL2 language reference *table* —
it says each operator's precedence relative to the others, but is silent on
how a chain of *prefix* operators with different precedences should compose.
But the wider parsing literature is not silent on it: the shape here is a
textbook "operator-style" deep priority conflict, the community's own stated
"correct" reading for it is merc's (the low-precedence prefix swallows the
higher-precedence infix, regardless of what wraps it), and mCRL2's answer is
the specific failure mode that ~25 years of work on declarative
disambiguation (Klint & Visser 1994 through Amorim et al. 2018) documents for
parsers that resolve priority with a flat, un-rewritten, per-production table
— which is exactly what `mcrl2_syntax.g`'s `right N` annotations are. Read
that way, this isn't "two independently reasonable readings that happen to
disagree" so much as "merc's Pratt parser is architecturally immune to a bug
class that mCRL2's chosen disambiguation mechanism is documented to be
vulnerable to, and here it's vulnerable."

**Recommendation:** keep merc's Pratt-parser reading. It's simpler,
predictable, matches what the documented precedence table gives when applied
compositionally, and — per the literature above — is the reading a properly
disambiguated grammar is supposed to produce for this exact shape. merc is a
compatible reimplementation of mCRL2's *language*, not a bug-for-bug clone of
dparser's disambiguation internals, and replicating this specific quirk
(special-casing "prefix operator directly wrapping a quantifier" to truncate
it) would mean deliberately reintroducing a documented parser bug class for
the sake of matching a parser that itself doesn't implement the fix. If exact
round-tripping through both toolchains ever matters for a spec that hits this
shape, the practical fix is the same one that resolves the ambiguity for a
human reader: parenthesize the quantifier explicitly (`!(exists d: D . X) &&
Y` or `!(exists d: D . X && Y)`, whichever was meant) rather than relying on
either parser's implicit reading.
