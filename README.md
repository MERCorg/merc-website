# Overview

The main website for the `merc` project, built using
[Zensical](https://zensical.org) (a replacement for
[MkDocs](https://www.mkdocs.org/)) and hosted on GitHub Pages. It uses the
[Material](https://squidfunk.github.io/mkdocs-material/) theme for a modern
design. First the submodules must be initialized and updated:

```bash
git submodule update --init
```

Then the required [Python](https://www.python.org/) dependencies must be
installed. Ideally using a virtual environment and the following command:

```bash
pip install -r requirements.txt
```

Furthermore, we use a `latex-math` MkDocs plugin to render LaTeX equations in
the documentation. During development it can be useful to install packages as
editable using the following command:

```bash
pip install -e plugins/zensical-latex-math
```

The plugin renders each fenced ` ```math ` block (and inline `$...$`) to an
SVG via `preview`'s tight crop, all at the same fixed `\fontsize` (see
`_MATH_FONT_PT` in `plugins/zensical-latex-math/latex_math.py`). It then
rewrites the SVG's pt-based width/height to `em`, relative to that same
`_MATH_FONT_PT`, so the rendered math scales with whatever font-size is in
force where it's inlined instead of a fixed pixel size — no CSS stretching
to the container width involved, so a rendered block always comes out at the
same font size as the surrounding text. `docs/stylesheets/extra.css`'s
`.latex-math-block` centers the block and lets it scroll horizontally if
it's wider than the viewport. A fenced block's info string can carry extra
tags after `math`, e.g. ` ```math algorithm `; each tag becomes a
`.latex-math-block--<tag>` modifier class on the wrapper `<div>` (see
`_extra_classes` in `latex_math.py`) alongside the base
`.latex-math-block`, and it's up to `extra.css` to give a tag meaning —
`--algorithm` left-aligns instead of centering, since pseudocode reads like
code, not a centered display equation. This is a hint you give directly in
the markdown, not something the plugin infers from the LaTeX body, so it
doesn't depend on guessing which environments/macros count as what.

One thing to watch for with `algorithmic` blocks: `algpseudocode`
right-justifies `\Comment` with `\hfill` to the page's `\linewidth`, and
`preview`'s tight crop bakes that blank gap into the SVG's bounding box. The
block no longer gets visually squeezed by this (nothing is stretched or
shrunk to fit), but it does still make the block itself much wider —
measured on `zielonka.md`'s algorithm, 119em with the default right-justify
vs. 52.6em with the override below — which just means more of the block
sits past the fold, behind a horizontal scrollbar. Redefine the comment
inline instead: `\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$
#1}` (see `docs/developer/symmetry/canonicalize-orbit.md`), and move a
`\Comment` whose text is long relative to its `\State` line to its own
`\Statex \Comment{...}` line so it doesn't dominate that line's width. A
generous `paperwidth` in `math_preamble` (e.g. `paperwidth=40cm`) is still
useful to give `\linewidth` enough room that long `\State` lines don't wrap
— it no longer has any effect on the rendered font size.

The documentation can then be served locally or built using the following commands:
* `zensical serve` - Start the live-reloading docs server.
* `zensical build` - Build the documentation site.

