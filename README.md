# Overview

The main website for the `merc` project, built using [MkDocs](https://www.mkdocs.org/) and hosted on GitHub Pages. It uses the [Material](https://squidfunk.github.io/mkdocs-material/) theme for a modern design. First of all, the require [Python](https://www.python.org/) dependencies must be installed. Ideally, this is done in a virtual environment.

```bash
pip install -r requirements.txt
```

Furthermore, we use a local `embed-latex` MkDocs plugin to render LaTeX equations in the documentation.

```bash
pip install -e plugins/mkdocs-latex-math
```

The documentation can be then be served locally or built using the following commands:
* `mkdocs serve` - Start the live-reloading docs server.
* `mkdocs build` - Build the documentation site.

