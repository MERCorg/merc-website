# merc-website

Source of the documentation site of the `merc` project
(<https://mercorg.github.io/merc-website/>), built with
[Zensical](https://zensical.org) and the Material theme. Pages are Markdown
under `docs/`, the navigation is the `nav` array in `zensical.toml`, and math
is rendered by the `latex_math` extension from the `plugins/zensical-latex-math`
submodule (see `README.md` for how it renders).

## What this site documents

The site is the precise, architecture-level documentation of `merc`: the
**definitions** the tool is built on, the **theorems** it relies on, and the
**architecture** (crates, phases, data flow, design decisions) that implements
them. It is not a tutorial and it does not duplicate API documentation. It
draws on three sources of truth, which are expected as sibling checkouts of
this repository:

| source | checkout | what it is authoritative for | published at |
|---|---|---|---|
| [MERCorg/merc](https://github.com/MERCorg/merc) | `../merc` | Rust implementation: crates, tools, flags, behaviour | rustdoc at <https://mercorg.github.io/merc/> |
| [MERCorg/merc-verified](https://github.com/MERCorg/merc-verified) | `../merc-verified` | Lean 4 formalisations: definitions and proved theorems (`MercLib/`, `MercVerified/`) | source on GitHub; doc-gen4 site not yet live |
| verified-machine-numbers | `../verified-machine-numbers` | Lean 4 formalisation of mCRL2's machine-number sorts | not published; do not link without asking |

When a page states what the code does or what is proved, check it against the
source above rather than against another page. The code and the Lean files
win; a page that disagrees with them is the thing to fix (or to flag, if the
code looks wrong). `../merc-verified/EXPORTS.md` lists every exported Lean
declaration and which ones are headline theorems; its `AGENTS.md` explains
which Lean files are human-vetted specs and which are generated proofs.

What belongs where, following `docs/developer/documentation.md`:

- **rustdoc** (in `../merc`): pre- and postconditions of functions, item-level
  behaviour. Pages link to it, they do not restate it.
- **crate `README.md`** (in `../merc`): usage and purpose of one crate.
- **this site**: the mathematics and the design across crates: definitions,
  theorems and their proof status, algorithms in pseudocode, and why the
  architecture is shaped the way it is.

## Layout

- `docs/index.md` — landing page.
- `docs/tools/` — usage of the command-line tools.
- `docs/developer/` — one directory per topic (parsing, typechecking,
  rewriting, pbes, parity, symbolic, symmetry, ...), each a multi-page
  section in `nav`.
- `docs/maintainers/` — release and publishing procedures.
- `docs/stylesheets/extra.css` — site CSS, including the `.latex-math-block`
  classes the math plugin emits.
- `linearisation/` — draft pages not yet under `docs/` or in `nav`.
- `site/` — build output (gitignored); never edit it.

## Commands

```bash
git submodule update --init                  # plugins are submodules
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt              # needs latex and dvisvgm on PATH
zensical serve                               # live preview at http://127.0.0.1:8000
zensical build --strict                      # what CI builds
```

CI (`.github/workflows/doc.yml`) runs the strict build and a `lychee` link
check on `site/`. Run the `docs-check` skill before saying a change is done.

## Writing conventions (summary)

The `write-docs` skill has the full conventions; the essentials:

- Dense, exact prose. Every claim about behaviour or correctness is traceable
  to code, a Lean declaration, or a cited paper.
- Formal content as numbered, bold-labelled paragraphs:
  `**Definition 3 (name).**`, `**Theorem 5 (name).**`, `**Conjecture 1 (name).**`.
  Numbering runs across the pages of a section; reuse it exactly.
- State the proof status of every theorem: proved in Lean (with the
  declaration name), proved on paper, or open.
- Rust items link to rustdoc:
  `` [`Item`](https://mercorg.github.io/merc/<crate>/<path>/<kind>.Item.html) ``.
- Lean claims link to their spec file:
  `` [`Name`](https://github.com/MERCorg/merc-verified/blob/main/<path>.lean) ``.
- `merc` in lowercase in prose; `MERC` only in the project or org name.
- Math in `$...$` and fenced `` ```math `` blocks; pseudocode as
  `` ```math algorithm `` with `algpseudocode`.

## Agent setup

These instructions are tool-agnostic; any coding agent working in this repo
follows them.

- `AGENTS.md` (this file) is the single source of project instructions.
  `CLAUDE.md` only imports it (`@AGENTS.md`) for Claude Code; other agents
  read `AGENTS.md` directly. Edit this file, never `CLAUDE.md`.
- Skills live in `.agents/skills/<name>/SKILL.md` (frontmatter with `name`
  and `description`, then Markdown). `.claude/skills` is a symlink to the same
  directory for Claude Code. Add new skills under `.agents/skills/` only.
  Load the matching skill before starting a task it covers.
- `.claude/agents/docs-reviewer.md` is a thin Claude Code subagent that runs
  the `review-docs` skill; the skill is the source of the review rules.

| skill | use it to |
|---|---|
| `write-docs` | write or edit a page: scope, structure, definitions and theorems, linking to rustdoc and Lean, adding a page to `nav` |
| `review-docs` | review new or edited pages for correctness against the sources and for consistency (read-only) |
| `docs-check` | run the CI checks locally: strict build, orphaned pages, link check |
| `docs-preview` | set up the environment and serve a live preview |
