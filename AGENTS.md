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

What belongs where, following `docs/contributing/documentation.md`:

- **rustdoc** (in `../merc`): pre- and postconditions of functions, item-level
  behaviour. Pages link to it, they do not restate it.
- **crate `README.md`** (in `../merc`): usage and purpose of one crate.
- **this site**: the mathematics and the design across crates: definitions,
  theorems and their proof status, algorithms in pseudocode, and why the
  architecture is shaped the way it is.

## Layout

- `docs/index.md` — landing page.
- `docs/tools/` — usage of the command-line tools.
- `docs/language/` — parsing, type checking and specifications.
- `docs/rewriting/` — `terms/`, `rewriters/` and `data/`.
- `docs/model-checking/` — PBES, symmetry, parity games and symbolic solving.
- `docs/benchmarks/` — all measured results (timings, node and step counts),
  since they change with the code; other pages state the design and link here.
- `docs/contributing/` — development guidelines, testing, documentation
  conventions, and release and publishing procedures.

The directories under `docs/` mirror the groups in `nav`. `merc` and
`merc-verified` cite page URLs, so moving a page needs an entry in the
`redirects` table of `zensical.toml`.
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

The pages are precise but not overwhelming, in an academic register. The
house style is `.agents/skills/write-docs/style.md` (structure rules S1 to
S7, register rules R1 to R8); the `write-docs` skill has the mechanics. The
essentials:

- The reader has a graduate background in formal methods and has not read
  merc's code. Every claim about behaviour or correctness is traceable to
  code, a Lean declaration, or a cited paper.
- A concept page is layered: abstract, definitions, algorithm, theorems,
  implementation, references. One topic per page, about 300 lines at most.
- Formal content as numbered, bold-labelled paragraphs with an anchor:
  `<a id="def-name"></a>**Definition 3 (name).**`. Numbering is per page and
  per kind; a statement on another page is referenced by a link naming that
  page, `[Parity games, Def. 1](parity_games.md#def-parity-game)`.
- State the proof status of every theorem: proved in Lean, proved on paper,
  or open. The Lean declaration is linked in the statement's own paragraph,
  `` [`Name`](https://github.com/MERCorg/merc-verified/blob/main/<path>.lean) ``;
  no "theorem | Lean" tables, and no Lean code inlined as pseudocode.
- Rust links are for key items only: the crate once per page and the public
  types that realise a definition, as
  `` [`Item`](https://mercorg.github.io/merc/<crate>/<path>/<kind>.Item.html) ``.
  Other public items are plain code spans, checked against `../merc` by hand.
  No private items, fields, files or line numbers.
- Declarative present tense; no em-dash asides, fillers or rhetorical
  contrast; italics only for a term being defined, bold only for statement
  labels; papers cited by key with a `## References` section.
- `merc` in lowercase in prose; `MERC` only in the project or org name.
- Math in `$...$` and fenced `` ```math `` blocks; pseudocode as
  `` ```math algorithm `` with `algpseudocode`, in the page's notation.

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
| `write-docs` | write or edit a page: house style (`style.md`), structure, definitions and theorems, linking to rustdoc and Lean, adding a page to `nav` |
| `review-docs` | review new or edited pages for correctness against the sources, consistency and house style (read-only) |
| `docs-check` | run the CI checks locally: strict build, orphaned pages, link check, and the advisory style lint |
| `docs-preview` | set up the environment and serve a live preview |
