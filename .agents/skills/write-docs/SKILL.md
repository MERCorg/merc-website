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
- **Sibling pages.** Read the other pages of the section: their definitions,
  numbering, notation and macros are what the new text continues.

If the code, the Lean statement and an existing page disagree, say so to the
user instead of silently picking one.

## 2. Structure of a page

- Start with a `# Title` heading; no frontmatter. A ```` ```math_preamble ````
  block may come first when the page needs LaTeX packages or macros.
- First paragraph: what the page defines, where `merc` implements it (crate
  link and, where relevant, the tool and flag), and what it assumes from
  sibling pages ("This page assumes Definitions 1 to 8 on [...]"). A
  multi-topic page then lists what it covers, in order.
- Then the content, typically: overview or idea → definitions → algorithm
  (pseudocode) → theorems → how the implementation maps onto them →
  references. Omit sections that have nothing to say.

## 3. Definitions, theorems and proof status

- Formal statements are bold-labelled paragraphs, numbered within a section
  (all pages under one `nav` group share one numbering):

  ```markdown
  **Definition 9 (filter).** For an Even vertex $v$, ...

  **Theorem 7 (termination).** H-B terminates from every initial profile.

  **Conjecture 1 (polynomial iterations).** ...
  ```

  Continue the numbering of the sibling pages; never renumber existing
  items without updating every reference to them across the section (grep
  for `Definition <n>` / `Theorem <n>`).
- Define every symbol before its first use, or refer to the definition that
  introduces it. Use one notation per concept across the section.
- A statement is either a definition, a theorem (with its status), or
  explicitly marked as a conjecture or an open question. Do not present an
  unproved claim as a fact in prose.
- State the proof status of every theorem: proved in Lean, proved on paper
  only (cite where), or open. When some theorems are in Lean, end the
  section with a table mapping each to its Lean claim:

  ```markdown
  | theorem | Lean |
  |---|---|
  | Theorem 6 | [`HBCorrect`](https://github.com/MERCorg/merc-verified/blob/main/MercLib/HybridSI/Correctness.lean) |
  | Conjecture 1 | `HBPolyIterations`, open |
  ```

  Cite the spec-file `def ... : Prop` (the statement a reader should check),
  not the proof's `theorem`. If the Lean statement is weaker or differs from
  the page's (an extra fuel bound, a finiteness assumption), say how.
- A *Proof idea* after a theorem is welcome when it explains the structure;
  full proofs belong in Lean or the cited paper.

## 4. Architecture

When describing how the code implements the mathematics:

- Name the crates and the key types or traits, linked to rustdoc, and say
  which definition each one realises.
- Describe data flow and phase boundaries across crates, invariants a type
  maintains, and the reason for a design choice (the alternative and why it
  was rejected). Leave per-function pre- and postconditions to rustdoc.
- Do not name private helpers, fields or line numbers; they change without
  the page noticing.

## 5. Formatting and links

- **Rust items** link to rustdoc, link text in backticks, the last segment of
  the text matching the item in the URL:
  - items: `` [`Item`](https://mercorg.github.io/merc/<crate>/<module/path>/<kind>.Item.html) ``
    where `<kind>` is `struct`, `enum`, `trait`, `fn`, `type`, `macro`, ...
  - crates and modules: `` [`name`](https://mercorg.github.io/merc/<crate>/<module/path>/index.html) ``

  Derive `<crate>` (with underscores, e.g. `merc_vpg`) and the module path
  from `../merc` — a re-exported item lives under the path it is re-exported
  at.
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
- **Admonitions**: `!!! note "Title"` where neighbouring pages use them.
- **Names**: `merc` in lowercase in prose; `MERC` only in "The MERC Project"
  and `MERCorg`. Tool names as invoked (`merc-vpg solve --solver hybrid-si`).

## 6. Adding a new page

1. Choose the section by topic from `nav` in `zensical.toml` and the
   directories under `docs/`. Create a new section only when the user asks
   for one.
2. Create `docs/<section path>/<slug>.md` with a kebab-case slug.
3. Add it to the section's array in `nav`, at the position its reading order
   requires (after the pages whose definitions it uses), not at the end by
   default.
4. Link to it from the sibling pages that should point readers to it.

## 7. Before handing back

Run the `docs-check` skill (strict build, orphaned pages, link check), and
for substantial changes the `review-docs` skill. Report which Lean and code
claims you verified and which you could not.
