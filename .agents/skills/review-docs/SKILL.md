---
name: review-docs
description: Review new or edited merc-website pages for correctness against the merc Rust code and the Lean formalisations, and for consistency — definition and theorem numbering, proof-status claims, rustdoc and Lean links, cross-links, terminology and nav. Read-only; reports findings. Use after writing or substantially editing documentation, or when asked for a docs review.
---

# review-docs

The pages under review are precise, reference-style documentation of `merc`:
definitions, theorems and architecture. Your job is to find what is **wrong
or inconsistent**, not to rewrite prose to your taste. The style is
deliberately dense; do not ask for shorter sentences or a gentler tone.

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

If a sibling checkout is missing, say which claims you could not verify.

**2. Numbering and cross-references.** Definitions, theorems and
conjectures are numbered across a section's pages
(`**Definition 9 (filter).**`). Check that new items continue the numbering
without gaps or duplicates, and that every `Definition n`, `Theorem n`,
step or paper reference in the change points at the item with that number
and name in the page that defines it. Derive the numbering from the files;
grep the whole section. These silently drift when one page is edited and its
neighbours are not.

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
- Do not try to fetch external URLs; check structure and the local
  checkouts only.

**4. Precision.** Symbols used before they are defined, one concept under
two notations within a section, an algorithm in pseudocode that disagrees
with the definition it implements, or a page restating per-function rustdoc
instead of linking to it.

**5. Terminology.** `merc` in lowercase in prose; `MERC` only in "The MERC
Project" and `MERCorg`. Flag inconsistent naming of the same concept across
the section.

**6. Nav.** Every page under `docs/` has an entry in `nav` in
`zensical.toml`. Run the orphaned-pages command from the `docs-check` skill
and report what it prints.

## Output

A flat list, most important first. Each finding: file and line, one
sentence stating the problem, and the evidence (the code, Lean declaration,
or other page it contradicts, quoted or cited). Then one line naming the
claims you could not verify and why. If nothing is wrong, say so plainly;
do not invent minor findings to fill the list.
