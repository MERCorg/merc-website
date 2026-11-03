---
name: docs-preview
description: Set up the local environment and run a live-reloading preview of the merc-website docs (Zensical/Material). Use when the user wants to serve, preview, or "see" the docs locally, or is starting fresh work on this repo and needs the environment working.
---

# docs-preview

Gets the Zensical dev server running against this repo's docs so changes can
be previewed live at `http://127.0.0.1:8000`.

## Steps

1. **Initialize submodules.** Local plugins are git submodules (see
   `.gitmodules`), and `requirements.txt` installs them from their local
   paths, so they must be checked out before installing:

   ```bash
   git submodule update --init
   ```

2. **Check system prerequisites.** Math is rendered by a LaTeX-based
   markdown extension, which needs `latex` and `dvisvgm` on `PATH` (CI
   installs `texlive-full` and `dvisvgm`; see `.github/workflows/doc.yml`):

   ```bash
   command -v latex && command -v dvisvgm
   ```

   If either is missing, tell the user what to install rather than
   installing system packages yourself.

3. **Set up the Python environment.** Always install into a virtualenv,
   never the system Python:

   ```bash
   [ -d .venv ] || python3 -m venv .venv
   source .venv/bin/activate
   command -v zensical || pip install -r requirements.txt
   ```

   If a plugin needs local edits (only if the user is also working on the
   plugin itself), install it editable: `pip install -e <plugin path>`.

4. **Serve.**

   ```bash
   zensical serve
   ```

   It is a long-running dev server with live reload, not a one-shot
   command: start it as a background process if your environment supports
   that, otherwise ask the user to run it in a separate terminal. Never run
   it in the foreground and wait for it to exit.

5. Report the local URL back to the user instead of trying to screenshot or
   curl it yourself unless they ask for a specific rendered check.

## Notes

- `zensical build` (no `serve`) does a one-shot static build into `site/` —
  use that instead if the goal is just to confirm the site builds, and
  prefer the `docs-check` skill if the goal is to validate correctness
  (strict build + link check) rather than preview.
