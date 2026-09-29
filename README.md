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

The plugin renders each fenced ` ```math ` block (and `math_preamble`) to an
SVG at its natural LaTeX point size and `preview` crops it tightly to content;
`docs/stylesheets/extra.css` then stretches that SVG to the page width via
`.latex-math-block`. Two things make a rendered `algorithmic` block come out
tiny even though nothing errors:

1. **The `.latex-math-block` CSS rule missing.** Without it the SVG renders
   at LaTeX's native point size instead of being stretched — check
   `extra.css` first if diagrams look undersized.
2. **`\Comment` left at its default right-justified style.** `algpseudocode`
   right-justifies `\Comment` with `\hfill` to the page's `\linewidth`, which
   `math_preamble` sets very wide (e.g. `paperwidth=40cm`) so long comments
   fit. `preview`'s tight crop bakes that whole blank gap into the SVG's
   bounding box, so stretching it to the page width shrinks the actual
   pseudocode instead of the gap. Every `math_preamble` using
   `algpseudocode` should instead redefine the comment inline:
   `\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}` (see
   `docs/developer/symmetry/canonicalize-orbit.md`), and a `\Comment` whose
   text is long relative to its `\State` line should move to its own
   `\Statex \Comment{...}` line so it doesn't dominate that line's width.

The documentation can then be served locally or built using the following commands:
* `zensical serve` - Start the live-reloading docs server.
* `zensical build` - Build the documentation site.

