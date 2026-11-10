
Although it is never clear what is the best way to document a codebase, we have
some general guidelines that we try to follow in the `merc` project. Ideally, we
want the documentation close to the place where it is relevant, so no big UML
diagrams that have no relation to the source of truth, i.e., the code.

## Code

All code should contain documentation explaining the pre and post conditions of
the functions in the code, in the form of `rustdoc` comments. These comments can
use basic Markdown for formatting, and refer to other items in the codebase
using intra-doc links. Examples should be denoted as ```rust` code blocks, such
that they are tested as part of `rustdoc` tests.

## Crates

Each crate should contain a `README.md` file in its root directory that explains
the basic usage of the crate, and explains its overall purpose. This file can
also contain basic overall architecture of the crate, and should link to
relevant papers that the techniques in the crate are based on.

## Tools

For tools the documentation should focus on the usage of the tool, i.e., provide
more general text about what workflows the tools are part of, and general flags
that should be used in the tool. 

## Design documents

The pages of this site document the design across crates: the **definitions**
the code is built on, the **theorems** it relies on, and the **architecture**
that implements them. They are written like the preliminaries of a paper, not
as a tutorial or a changelog.

- Formal statements are bold-labelled and numbered per page, each kind
  separately, such as **Definition 3 (attractor).** and **Theorem 2
  (termination).**, and each has an anchor named after the concept, written
  as inline HTML before the label: `<a id="def-attractor"></a>`. Adding a
  statement then renumbers only its own page, and links to it keep working.
  Definitions from a paper cite the paper's own number, for example
  "([LWW22], Definition 4)".
- A page restates the definitions and theorem statements it uses, also those
  from a paper, in the notation of its section, so that it can be read on its
  own; pseudocode is rewritten in that notation rather than copied. Proofs,
  examples and variants that merc does not implement are only cited. Where merc
  deviates from the paper, the page states both and the difference.
- Every theorem states its proof status: proved in Lean (with a table mapping
  each theorem to its statement in
  [merc-verified](https://github.com/MERCorg/merc-verified)), proved on paper
  (cite where), or open, in which case it is a conjecture. A claim that is only
  measured is an observation. When the Lean statement is more abstract than the
  implementation, for example sets instead of LDDs, the page says so.
- The architecture is described in terms of the definitions: which crate or
  public type realises which definition, the order of the phases, the invariants
  a type maintains, and why a design was chosen over the alternative.
  Per-function details belong in rustdoc, and private helpers, fields, file
  names and line numbers do not belong on these pages at all, since they change
  without the page noticing.
- Document what is implemented. Plans and proposals belong in an issue until the
  code exists.

### Links

Links are checked, names are not: CI runs `lychee` on every page, so a link to
an item that is renamed, moved or removed fails the build, whereas a name in
backticks goes stale without anyone noticing. Every public item a page mentions
is therefore linked, at least at its first mention on the page.

- Rust: link public items to their rustdoc page, such as
  [`LabelledTransitionSystem`](https://mercorg.github.io/merc/merc_lts/struct.LabelledTransitionSystem.html),
  and crates or modules to their `index.html`. Link a method through the page
  of its type, `struct.LabelledTransitionSystem.html#method.relabel`; `lychee`
  checks the fragment as well, so a renamed method fails the build. Do not
  link source files, which move with every refactoring.
- Lean: link a declaration to the spec file that states it in
  [merc-verified](https://github.com/MERCorg/merc-verified), until the doc-gen4
  site is published and declarations can be linked directly.
- Examples: link the example's directory and give the command that runs it,
  such as `cargo run -p merc_pbes --example write_srf_capture`.
- Website: link a section by an explicit anchor, `## Well-typedness {#well-typedness}`,
  so that rewording the heading keeps the link. A bare "Definition 4" refers to
  the current page; a statement on another page is always a link that names
  that page, `[Parity games, Definition 1](parity_games.md#def-parity-game)`,
  so that `lychee` reports it when the statement moves or its anchor changes.
- Papers: cite them with their own definition and theorem numbers, and link the
  DOI.

The same rules apply the other way around. A rustdoc comment or a Lean docstring
cites the paper a definition comes from, and links the website section only for
definitions that originate in merc, since the website is then their only written
definition. They never repeat the explanation of the website.

