# Overview

The main website for the `merc` project, built using [Zensical](https://zensical.org) (a replacement for [MkDocs](https://www.mkdocs.org/)) and hosted on GitHub Pages. It uses the [Material](https://squidfunk.github.io/mkdocs-material/) theme for a modern design. First the submodules must be initialized and updated:

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
pip install -e 3rd_party/zensical-latex-math
```

The documentation can then be served locally or built using the following commands:
* `zensical serve` - Start the live-reloading docs server.
* `zensical build` - Build the documentation site.

