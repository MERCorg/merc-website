---
name: write-docs
description: Write or edit technical documentation pages for merc-website — precise definitions, theorems with their Lean proof status, algorithms, and the architecture of the merc Rust code — and add new pages to the zensical.toml nav. Use when asked to document a concept, algorithm, crate or design decision, to add or restructure a doc page, or to bring a page in line with the code or the Lean formalisation.
---

# write-docs

Pages on this site are the precise reference for `merc`: what its objects
*are* (definitions), what is *true* of them (theorems, with proof status), and
how the Rust code *implements* them (architecture). Write them the way a
paper's preliminaries or a language reference is written, not as a tutorial.
`AGENTS.md` lists the three sources of truth (`../merc`, `../merc-verified`,
`../verified-machine-numbers`); this skill is about turning them into pages.

**Read [`style.md`](style.md) in this directory before writing.** It is the
house style: who the reader is, the structure rules S1 to S7 that keep a page
from overwhelming them, the register rules R1 to R8, and the shape of the
page types other than concept pages (section index, tool, benchmark,
contributing). The sections below are the mechanics; where they are silent,
`style.md` decides.

## 1. Gather the facts before writing

Nothing on a page is written from memory or from another page alone.

- **Code.** Read the crate in `../merc` that implements the topic: its
  `README.md`, the public types and functions the page will name, and the
  tool's CLI flags if the page mentions how to run it. Record the exact crate
  and module path of every item you will link.
- **Lean.** Search `../merc-verified` (`MercLib/`, `MercVerified/`) and
  `../verified-machine-numbers` for the topic. Each formal claim is a named
  `def <Claim> : Prop` in a human-vetted spec file, proved by a `theorem` in
  the matching `Proofs/*_Proofs.lean`. `../merc-verified/EXPORTS.md` lists the
  exported declarations and marks the headline ones. A claim is *proved in
  Lean* only if its proof contains no `sorry` and no `axiom` beyond those
  `EXPORTS.md` lists; check with `grep -n sorry` on the proofs file rather
  than assuming.
- **Papers.** When a definition or algorithm comes from a paper, have the
  paper's own numbering at hand (Definition 4.2, Algorithm 3) so the page can
  cite it exactly.
- **Sibling pages.** Read the other pages of the section: their definitions
  and their anchors (to link to), notation and macros are what the new text
  continues.

If the code, the Lean statement and an existing page disagree, say so to the
user instead of silently picking one.

## 2. Structure of a page

- Start with a `# Title` heading; no frontmatter. A ```` ```math_preamble ````
  block may come first when the page needs LaTeX packages or macros.
- Follow the layers of `style.md` S1: abstract, definitions, algorithm,
  theorems, implementation, references. Omit layers that have nothing to say.
- The abstract is one paragraph: what the page defines, where `merc`
  implements it (crate link and, where relevant, the tool and flag), and what
  it assumes from other pages ("It assumes [Parity games, Definitions 1 to
  9](parity_games.md#def-parity-game)"). This is the one place where the
  prerequisites are listed (S7).
- Before adding to a page, check its length (S2) and whether the new
  statement earns a number (S3). When a page passes about 300 lines, propose
  a split to the user instead of appending.

## 3. Definitions, theorems and proof status

- Formal statements are bold-labelled paragraphs at the start of a line,
  numbered per page and per kind (definitions, theorems, conjectures, ...
  each from 1), and each preceded by an anchor named after the concept,
  with a prefix for the kind (`def-`, `thm-`, `lem-`, `cor-`, `prop-`,
  `conj-`):

  ```markdown
  <a id="def-filter"></a>**Definition 1 (filter).** For an Even vertex $v$, ...

  <a id="thm-termination"></a>**Theorem 2 (termination).** H-B terminates from every initial profile.

  <a id="conj-polynomial-iterations"></a>**Conjecture 1 (polynomial iterations).** ...
  ```

  The anchor is inline HTML rather than `{#id}`, because `lychee` reads
  `id`s from HTML in Markdown but `{#id}` only on headings. Keep an anchor
  when renumbering or rewording, so that links to it stay valid.
- A bare `Definition 3` means Definition 3 of the current page. A statement
  on another page is always referenced by a link that names the page:
  `[Parity games, Def. 1](parity_games.md#def-parity-game)`, or for
  several, `[Strategy improvement, Defs. 1 to 7](strategy-improvement.md#def-relevance-order)`
  linking the first. A long page title may be shortened in the link text as
  long as it still identifies the page. Cite where the argument needs it, not
  after every clause (S7). Inserting a statement renumbers its own page only:
  update the references on that page, and grep the site for links to that
  page whose number changed.
- Define every symbol before its first use, or refer to the definition that
  introduces it. Use one notation per concept across the section.
- A paper's own numbers are always cited with the paper, "([EG21],
  Definition 4)", so they cannot be mistaken for the page's.
- A statement is either a definition, a theorem (with its status), or
  explicitly marked as a conjecture or an open question. Do not present an
  unproved claim as a fact in prose.
- State the proof status of every theorem in its own paragraph: proved in
  Lean, proved on paper only (cite where), or open. A formalised statement
  links its Lean declaration right there, and a formalised definition does
  the same ("Formalised in Lean as ..."):

  ```markdown
  <a id="thm-correctness"></a>**Theorem 1 (correctness).** ... Proved in Lean as
  [`HBCorrect`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/Algorithms/ParityGame/HybridSI/Correctness.lean).
  ```

  Do not collect these in a "theorem | Lean" table at the end of a section;
  when editing a page that has one, move each link to its statement and
  delete the table. Link the spec-file `def ... : Prop` (the statement a
  reader should check), not the proof's `theorem`. If the Lean statement is
  weaker or differs from the page's (an extra fuel bound, a finiteness
  assumption), the same sentence says how. An open claim is a conjecture and
  names its Lean statement without a proof claim.
- Do not inline Lean code as the page's pseudocode (S4). The page gives the
  algorithm in its own notation and links the Lean definition as the
  executable form.
- A *Proof idea* after a theorem is welcome when it explains the structure;
  full proofs belong in Lean or the cited paper.

## 4. Implementation

When describing how the code implements the mathematics (S5):

- Say which crate and which public type or trait realises which definition;
  with more than two, as a table `| definition | realised by |`.
- Describe data flow and phase boundaries across crates, invariants a type
  maintains, and the reason for a design choice (the alternative and why it
  was rejected). Leave per-function pre- and postconditions to rustdoc.
- Do not name private helpers, fields, local variables, files or line
  numbers; they change without the page noticing. Keep Rust names out of
  definitions, theorems and pseudocode.
- Numbers that were measured (timings, node counts, step counts) go to
  `docs/benchmarks/`; the page states the design and links there.

## 5. Formatting and links

Link key items only (S6). CI's `lychee` check fails on a link whose target
was renamed, moved or removed, whereas a bare name in backticks goes stale
silently; but a page where every name is a link is unreadable, and a page
that names many items restates rustdoc. So:

- link the crate once per page;
- link the few public types or traits that realise a definition, at their
  first mention;
- write any other public item as a plain code span, and name it only if the
  reader needs the name to find the code. Verify in `../merc` that it exists
  under that name, since nothing else will;
- link every Lean declaration the page names, at its statement.

Before linking a Rust item, check that its crate is in the published rustdoc
(`https://mercorg.github.io/merc/`); if it is not yet, tell the user rather
than dropping the link.

- **Rust items** link to rustdoc, link text in backticks, the last segment of
  the text matching the item in the URL:
  - items: `` [`Item`](https://mercorg.github.io/merc/<crate>/<module/path>/<kind>.Item.html) ``
    where `<kind>` is `struct`, `enum`, `trait`, `fn`, `type`, `macro`, ...
  - crates and modules: `` [`name`](https://mercorg.github.io/merc/<crate>/<module/path>/index.html) ``

  - methods and associated items: through their type's page,
    `` [`relabel`](https://mercorg.github.io/merc/<crate>/<path>/struct.Type.html#method.relabel) ``.
    CI runs `lychee --include-fragments`, so the `#method.name` fragment is
    checked too.

  Derive `<crate>` (with underscores, e.g. `merc_vpg`) and the module path
  from `../merc` — a re-exported item lives under the path it is re-exported
  at. Do not link source files on GitHub.
- **Lean declarations** link to their spec file on GitHub, link text the
  declaration name in backticks:
  `` [`Name`](https://github.com/MERCorg/merc-verified/blob/main/<path>.lean) ``.
  The doc-gen4 site (`https://mercorg.github.io/merc-verified/`) is not
  published yet and CI's link check would fail on it; switch to
  `https://mercorg.github.io/merc-verified/<Module/Path>.html#<Full.Name>`
  once it is live. Do not link `verified-machine-numbers` (not public);
  name the declaration and its file instead.
- **Other pages**: relative links, `[text](other-page.md#anchor)`; anchors
  are the heading lowercased with spaces as hyphens.
- **Math**: `$...$` inline, ```` ```math ```` for display, and
  ```` ```math algorithm ```` for `algpseudocode` pseudocode (left-aligned).
  In pseudocode, use
  `\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}` in the
  preamble and put a long `\Comment` on its own `\Statex` line, so the block
  does not become very wide (see `README.md`).
- **Papers**: cite by key, `[LWW22]`, and end the page with `## References`
  listing each key with authors, title, venue, year and DOI link (R8).
- **Emphasis**: italics only for a term where it is defined, bold only for
  statement labels (R5).
- **Admonitions**: sparingly, `!!! note "Title"` for a warning the reader
  must not miss; not for ordinary remarks.
- **Names**: `merc` in lowercase in prose; `MERC` only in "The MERC Project"
  and `MERCorg`. Tool names as invoked (`merc-vpg solve --solver hybrid-si`).

## 6. Adding a new page

1. Choose the section by topic from `nav` in `zensical.toml` and the
   directories under `docs/`. `nav` groups pages by subject (Language,
   Rewriting, Model checking, Contributing), and a page covers both the theory
   and the code of its topic, so do not separate them. Measured results go
   under `docs/benchmarks/`. Create a new section only when the user asks for
   one.
2. Create `docs/<section path>/<slug>.md` with a kebab-case slug.
3. Add it to the section's array in `nav`, at the position its reading order
   requires (after the pages whose definitions it uses), not at the end by
   default.
4. Link to it from the sibling pages that should point readers to it.

## 7. Before handing back

Reread the page once against `style.md` as its intended reader: can they stop
after each layer, and is every sentence needed? Then run the `docs-check`
skill (strict build, orphaned pages, link check, style lint), and for
substantial changes the `review-docs` skill. Report which Lean and code
claims you verified and which you could not.
