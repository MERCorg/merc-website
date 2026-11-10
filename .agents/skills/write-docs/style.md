# House style of the merc documentation

The single source of the writing rules. `write-docs` applies them,
`review-docs` checks them and cites them by number (S1 to S7, R1 to R8), and
`docs/contributing/documentation.md` is their public summary.

The aim is documentation that is **precise but not overwhelming**: every
statement is exact and traceable, and a page carries only what its reader
needs, in an order that lets them stop early.

## Reader

The reader has a graduate background in formal methods and has not read
merc's code. They know from the literature what a parity game, a rewrite
system or a decision diagram is. They do not know merc's types, its phases,
or where it deviates from a paper. They read a page to learn what merc
computes, why that is correct, and which part of the code does it.

Write nothing the reader already knows from a textbook, and assume nothing
they could only know from the source.

## Structure rules

**S1. Layered page.** A concept page has these layers, in this order, and
omits the ones with nothing to say:

1. *Abstract*: one paragraph. What the page defines, which crate implements
   it (linked) and under which tool and flag, and what it assumes from other
   pages. A long page then lists what it covers.
2. *Definitions*, with a labelled example where a definition is not obvious.
3. *Algorithm*, in pseudocode.
4. *Theorems*, each with its proof status.
5. *Implementation*: which public type realises which definition, and the
   design decisions.
6. *References*.

Each layer can be read without the layers after it. A reader who stops after
the abstract knows what the page is for; one who stops after the theorems
knows the mathematics without having seen a Rust name.

**S2. One topic, bounded length.** A page covers one concept or one
algorithm. About 300 lines is the soft limit. A longer page is split by
topic, or loses what belongs elsewhere: measured results go to
`docs/benchmarks/`, per-item behaviour to rustdoc, usage to `docs/tools/`.

**S3. A statement earns its number.** A definition is numbered only if it is
used later on the page or linked from another page. A notion used once is
introduced in a sentence, with the term in italics. A theorem is numbered
only if `merc` relies on it or the page argues from it.

**S4. Pseudocode in the page's notation.** Pseudocode is given for an
algorithm that is merc's own, or where merc deviates from the cited paper;
an algorithm merc takes over unchanged is cited. It uses the symbols of the
page's definitions, never Rust identifiers, and there is one block per
algorithm. Lean code is not inlined as pseudocode: a copy goes stale
unnoticed and carries proof-engineering arguments (fuel, decidability
instances) that the reader does not need. Link the Lean definition as the
executable form instead (S6).

**S5. Implementation in terms of the definitions.** The implementation
section says which crate or public type realises which definition (a short
table when there are more than two), the order of the phases, the invariants
a type maintains, and for each design decision the alternative and why it was
rejected. It names no private helper, field, local variable, file or line
number. Rust names do not appear inside a definition or a theorem.

**S6. Links to key items only, and to Lean at the statement.**

- *Rust.* Link the crate once per page, and the few public types or traits
  that realise a definition, at their first mention. Other public items are
  plain code spans, and a page names few of them: a name that is not needed
  to find the code is left to rustdoc.
- *Lean.* A definition or theorem that is formalised links its Lean
  declaration in the statement's own paragraph, not in a table at the end of
  the section:

  ```markdown
  <a id="thm-correctness"></a>**Theorem 1 (correctness).** H-B returns the
  winner of every vertex. Proved in Lean as
  [`HBCorrect`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Algorithms/ParityGame/HybridSI/Correctness.lean),
  for runs with fuel $|V|^{|V|} + 1$.
  ```

  For a definition: "Formalised in Lean as [`Game`](...)." Where the Lean
  statement is weaker than or differs from the page's, the same sentence says
  how.

**S7. Compact cross-references.** Prerequisites are named once, in the
abstract. After that, a statement on another page is cited where the argument
needs it, with a short link that names the page:
`[Desugaring, Def. 2](desugaring.md#def-hoisting)`. Do not attach a citation
to every clause, and do not repeat one within a paragraph. A section index
gives one sentence per page and no inventory of definition numbers.

## Register rules

**R1. Declarative present tense.** "The solver computes", "we write $\Xi$
for". Impersonal or "we"; never "you". No questions, no exclamations.

**R2. No asides.** No em-dash or parenthetical digressions. A remark that
matters is its own sentence; one that does not is deleted.

**R3. No fillers or intensifiers.** Not: actually, just, simply, basically,
literally, really, very, of course, obviously, essentially, note that, in
other words, easy to, happens to.

**R4. State what is, not what is not.** No rhetorical contrast ("not a
speed-up bolted onto a finished graph"), no scare quotes, no anthropomorphism
("nobody has seen", "hands her an escape"). A negative is stated only when
the reader would otherwise assume the positive, such as a deviation from the
paper.

**R5. Typography carries meaning.** Italics mark a term at the place it is
defined, and nothing else. Bold marks statement labels (**Definition 1
(name).**, **Example 2.**) and nothing else. Code spans are for names that
exist in the code or on the command line.

**R6. One term per concept.** Within a section, a concept has one name and
one symbol. A paper's differing term is mentioned once, where the concept is
defined.

**R7. Labelled examples.** An example is a paragraph labelled **Example n.**
placed after the definition it illustrates. One motivating example may come
before the first definition. Examples are small enough to check by hand.

**R8. Citations by key.** A paper is cited as `[LWW22]`, and its own numbers
always with the key: "([LWW22], Lemma 4)". The page ends with `## References`
listing each key with authors, title, venue, year and a DOI link. The
abstract does not quote the full reference.

## Example of the register

Before:

> A game explored on the fly never presents the solver with a complete
> graph: states and their successors are generated on demand, so at any point
> only a *partial* graph is available — each vertex may still turn out to
> have successors nobody has seen yet. The four partial solvers below are not
> a speed-up bolted onto a finished graph; they are how vertices get decided
> *during* exploration.

After:

> During on-the-fly exploration the solver sees a *partial game*
> $\mathcal G = (G, I)$: the graph $G$ explored so far and the set
> $I \subseteq V$ of *incomplete* vertices, whose successors are not yet all
> known. A partial solver decides vertices of $\mathcal G$ such that the
> decision holds in every extension of $\mathcal G$ (Theorem 1), so
> exploration stops as soon as the initial vertex is decided.

## Page types

S1 to S7 describe concept pages. The other kinds of page keep the register
rules and have their own shape:

| type | where | shape |
|---|---|---|
| section index | `index.md` of a section | one paragraph on what the section covers; the pages in reading order with one sentence each; an architecture overview (phases, crates, data flow) when the section has one |
| tool page | `docs/tools/` | what the tool or option does; synopsis; options; one worked command; a link to the concept page for the method |
| benchmark page | `docs/benchmarks/` | setup (machine, version, inputs, command); tables; one paragraph on what the numbers show; a link back to the design they measure |
| contributing page | `docs/contributing/` | procedures as numbered steps, conventions as rules with their reason |
