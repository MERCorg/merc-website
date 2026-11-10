---
name: review-docs
description: Review new or edited merc-website pages for correctness against the merc Rust code and the Lean formalisations, for consistency (definition and theorem numbering, proof-status claims, rustdoc and Lean links, cross-links, terminology, nav), and for the house writing style (structure and academic register). Read-only; reports findings. Use after writing or substantially editing documentation, or when asked for a docs review.
---

# review-docs

The pages under review are precise, reference-style documentation of `merc`:
definitions, theorems and architecture, written to be precise but not
overwhelming. Your job is to find what is **wrong, inconsistent, or against
the house style**. The house style is
`.agents/skills/write-docs/style.md`; read it first. A writing finding names
the rule it violates (S1 to S7, R1 to R8) and quotes the text. A preference
that no rule covers is not a finding.

Do not edit files. Report findings for someone else to act on.

## Scope

Review the changed pages: `git diff` and `git status` for uncommitted work,
`git diff main...HEAD` for a branch, or the pages the user names. Read the
whole page, not only the changed lines, and the sibling pages of its
section.

## What to check, most important first

**1. Claims against the sources of truth.** `AGENTS.md` lists them
(`../merc`, `../merc-verified`, `../verified-machine-numbers`). For every
concrete claim the change makes, check it there:

- Behaviour, types, crate names, tool names and flags: in `../merc`.
- "Proved in Lean": the named claim exists as a `def ... : Prop` in the
  Lean spec files, its proof in `Proofs/` contains no `sorry` (grep), and the
  Lean statement says what the page says — same hypotheses, no extra bound
  the page omits. `../merc-verified/EXPORTS.md` lists exported declarations
  and headline theorems.
- A theorem without stated proof status, or a claim presented as fact that
  is only conjectured, is a finding.
- Rust items named in plain code spans are not covered by the link check, so
  grep `../merc` for each: a name that does not exist (as a public item, or
  at all) is a finding.

If a sibling checkout is missing, say which claims you could not verify.

**2. Numbering and cross-references.** Definitions, theorems and
conjectures are numbered per page and per kind, from 1, each label at the
start of a line and preceded by an anchor
(`<a id="def-filter"></a>**Definition 1 (filter).**`). Check that a page's
numbers have no gaps or duplicates, that every statement has an anchor named
after its concept, and that every bare `Definition n` or `Theorem n` points at
the item with that number on the same page. A statement on another page must
be a link naming that page, `[Page title, Definition n](page.md#def-name)`,
whose number and name match the target; a bare number meant for another page
is a finding. A paper's numbers must be cited with the paper. Derive the
numbering from the files, and when a page was renumbered, grep the site for
links into it.

**3. Links.**

- Relative links `other-page.md#anchor`: the file exists and a heading in it
  produces the anchor (lowercased, spaces to hyphens, punctuation dropped).
- rustdoc: `` [`Item`](https://mercorg.github.io/merc/<crate>/<path>/<kind>.Item.html) ``
  or `` [`name`](https://mercorg.github.io/merc/<crate>/<path>/index.html) ``.
  The last segment of the link text matches the item in the URL, and where
  `../merc` is available, the item exists at that crate and module path with
  that kind.
- Lean: `` [`Name`](https://github.com/MERCorg/merc-verified/blob/main/<path>.lean) ``;
  the file exists in `../merc-verified` and declares `Name`. Links to the
  doc-gen4 site `mercorg.github.io/merc-verified` are findings while it is
  unpublished (they fail CI's link check). No links into
  `verified-machine-numbers`, which is not published.
- Key items only (S6): the crate is linked once on the page, and the public
  types or traits that realise a definition at first mention. An unlinked
  code span for another public item is fine. Findings are: no crate link, a
  key type never linked, the same item linked repeatedly, or a page that
  names so many items that it restates rustdoc.
- Every Lean declaration a page names is linked, in the paragraph of the
  statement it formalises. A "theorem | Lean" table at the end of a section
  is a finding (S6), as is Lean code inlined as pseudocode (S4).
- Links to Rust source files on GitHub, and names of private items, are
  findings.
- Do not try to fetch external URLs; check structure and the local
  checkouts only.

**4. Precision.** Symbols used before they are defined, one concept under
two notations within a section, an algorithm in pseudocode that disagrees
with the definition it implements, or a page restating per-function rustdoc
instead of linking to it.

**5. Structure (S1 to S7).** Per page:

- S1: is there a one-paragraph abstract saying what the page defines, where
  it is implemented and what it assumes? Do the layers come in order, and
  can the mathematics be read without the implementation section?
- S2: more than one topic, or well over 300 lines? Measured numbers outside
  `docs/benchmarks/`?
- S3: numbered definitions that nothing on the page or site refers to (grep
  the anchor and the number).
- S4: Rust identifiers in pseudocode; pseudocode for an algorithm taken over
  unchanged from the cited paper; two blocks for one algorithm.
- S5: private helpers, fields, local variables, file names or line numbers;
  Rust names inside a definition or theorem; a design decision without its
  reason.
- S7: the same cross-reference repeated in a paragraph, citations on every
  clause, a section index that inventories definition numbers.

A page of another type (section index, tool, benchmark, contributing) is
checked against its shape in the "Page types" table of `style.md` instead.

**6. Register (R1 to R8).** Run
`.agents/skills/docs-check/style-lint.sh <pages>` for the mechanical part
(em-dashes, fillers, bold outside labels, missing References), then read for
what a script cannot see: second person, rhetorical contrast and
anthropomorphism (R4), emphasis used for stress (R5), two names for one
concept (R6), unlabelled or oversized examples (R7), references quoted in the
abstract instead of a References section (R8). Report a recurring violation
once per page with a count and two or three quoted instances, not once per
line.

**7. Terminology.** `merc` in lowercase in prose; `MERC` only in "The MERC
Project" and `MERCorg`. Flag inconsistent naming of the same concept across
the section.

**8. Nav.** Every page under `docs/` has an entry in `nav` in
`zensical.toml`. Run the orphaned-pages command from the `docs-check` skill
and report what it prints.

## Output

Per page, in this form:

```
### <path>  (verdict: conforms | revise | rewrite)
Correctness
- <line>: <problem>. Evidence: <code, Lean declaration or page it contradicts>.
Structure
- <rule>, <line>: <problem>.
Writing
- <rule>, <count> instances, e.g. <line>: "<quoted text>".
```

Omit an empty group. The verdict is *conforms* when there is nothing or only
isolated writing findings, *revise* when the page has the right shape but
needs local fixes, and *rewrite* when its structure or register is wrong
throughout. Correctness findings do not change the verdict; they are listed
first because they matter most.

End with the pages ordered by how much work they need, and one line naming
the claims you could not verify and why. If a page has no findings, say so
plainly; do not invent minor findings to fill the list.
