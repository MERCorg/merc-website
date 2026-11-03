---
name: docs-check
description: Validate the merc-website docs the same way CI does before pushing or opening a PR — strict Zensical build, link check, and orphaned-page detection. Use after editing or adding pages under docs/, or when the user asks to check/validate the docs, check for broken links, or check the nav.
---

# docs-check

Reproduces what `.github/workflows/doc.yml` does on push/PR, locally, plus
one check CI doesn't do (orphaned pages missing from the nav). Run this
before telling the user docs changes are ready.

Assumes the environment is already set up (submodules, LaTeX tools,
`.venv` with `requirements.txt` installed). If the build fails on missing
modules, plugins or LaTeX binaries, run the setup steps of the
`docs-preview` skill first.

## Steps

1. **Strict build** — catches broken internal references, bad markdown
   extension syntax, and anything Zensical treats as a warning-as-error:

   ```bash
   if [ -d .venv ]; then source .venv/bin/activate; fi
   zensical build --strict
   ```

   Fix any reported errors before continuing. The strict build does not
   check that rustdoc or Lean links point at existing items; step 3 does,
   and the `review-docs` skill checks them against the local checkouts.

2. **Orphaned pages** — every file under `docs/` should be reachable from
   the `nav` array in `zensical.toml`. `zensical build --strict` does not
   flag a page that exists but isn't linked from `nav`, so check separately:

   ```bash
   comm -23 \
     <(cd docs && find . -name "*.md" | sed 's#^\./##' | sort) \
     <(grep -oE '"[A-Za-z0-9/_.-]+\.md"' zensical.toml | tr -d '"' | sort -u)
   ```

   Any path this prints exists in `docs/` but has no nav entry in
   `zensical.toml` — either add it to `nav` (see the `write-docs` skill)
   or confirm with the user it's intentionally unlisted (e.g. a page only
   reached via direct link).

3. **Link check** — CI runs `lychee` on the Markdown sources in `docs/`
   (not on `site/`), including the external rustdoc and Lean links, with
   `.lycheeignore` excluding hosts that reject non-browser clients. If
   `lychee` is available locally, run it with the arguments of the
   link-check step in `.github/workflows/doc.yml`:

   ```bash
   command -v lychee >/dev/null && lychee --no-progress --max-retries 3 --retry-wait-time 5 ./docs
   ```

   If `lychee` isn't installed, skip this step and say so explicitly rather
   than claiming links were checked — CI will still catch it, but the user
   should know it wasn't verified locally. Don't install a new global tool
   without asking first.

## Reporting

Summarize pass/fail per step. Don't just say "docs look good" — state
explicitly which of the three checks ran and which (if any) were skipped.
