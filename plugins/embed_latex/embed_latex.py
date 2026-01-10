import hashlib
import os
import re
import shlex
import subprocess
import tempfile
from typing import Any, Dict, Match, Pattern

from mkdocs.plugins import BasePlugin
from mkdocs.config import config_options


class EmbedLatexPlugin(BasePlugin):
    """
    MkDocs plugin: render LaTeX math (inline $...$, display $$...$$ and fenced blocks with info 'pdflatex')
    to SVG images using pdflatex + dvisvgm, storing results in site_dir/assets/latex cache.
    """

    config_scheme = (
        ("asset_subdir", config_options.Type(str, default="assets/latex")),
        (
            "pdflatex_cmd",
            config_options.Type(
                str, default="pdflatex -interaction=nonstopmode -halt-on-error"
            ),
        ),
        ("dvisvgm_cmd", config_options.Type(str, default="dvisvgm --no-fonts")),
    )

    def on_page_markdown(
        self, markdown: str, /, *, page: Any, config: Dict[str, Any], files: Any
    ) -> str:
        site_assets_dir: str = os.path.join(config["site_dir"], self.config["asset_subdir"])
        os.makedirs(site_assets_dir, exist_ok=True)

        # First replace fenced code blocks with info 'pdflatex' -> display math images
        markdown = self._replace_fenced_pdflatex(markdown, site_assets_dir)

        # Then handle $$...$$ display math
        markdown = self._replace_display_math(markdown, site_assets_dir)

        return markdown

    def _hash(self, tex: str, display: bool) -> str:
        h = hashlib.sha1()
        h.update(b"pdflatex_v1")
        h.update(b"\x01" if display else b"\x00")
        h.update(tex.encode("utf-8"))
        return h.hexdigest()

    def _render_to_svg(self, tex_body: str, display: bool, out_dir: str, basename: str) -> str:
        svg_path: str = os.path.join(out_dir, basename + ".svg")
        if os.path.exists(svg_path):
            return svg_path

        # Minimal document using preview to tightly crop the output
        env = r"""\documentclass{article}
\usepackage[active,tightpage]{preview}
\usepackage{amsmath,amssymb}
\begin{document}
\begin{preview}
%s
\end{preview}
\end{document}
"""
        if display:
            content: str = tex_body
        else:
            # inline: wrap in \(\)
            content = r"\(" + tex_body + r"\)"

        tex: str = env % content

        with tempfile.TemporaryDirectory() as td:
            tex_file: str = os.path.join(td, basename + ".tex")
            with open(tex_file, "w", encoding="utf-8") as f:
                f.write(tex)

            pdflatex_cmd = shlex.split(self.config["pdflatex_cmd"]) + [
                "-output-directory",
                td,
                tex_file,
            ]
            try:
                subprocess.run(
                    pdflatex_cmd,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                # on error, write a simple SVG placeholder
                with open(svg_path, "w", encoding="utf-8") as f:
                    f.write(
                        '<svg xmlns="http://www.w3.org/2000/svg"><text y="14">LaTeX error</text></svg>'
                    )
                return svg_path

            pdf_file: str = os.path.join(td, basename + ".pdf")
            dvisvgm_cmd = shlex.split(self.config["dvisvgm_cmd"]) + [
                pdf_file,
                "-o",
                svg_path,
            ]
            try:
                subprocess.run(
                    dvisvgm_cmd,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                # fallback: produce minimal SVG
                with open(svg_path, "w", encoding="utf-8") as f:
                    f.write(
                        '<svg xmlns="http://www.w3.org/2000/svg"><text y="14">Conversion error</text></svg>'
                    )
            return svg_path

    def _sanitize_alt(self, text: str) -> str:
        alt: str = text.replace('"', "'")
        alt = re.sub(r"\s+", " ", alt)
        return (alt[:120] + "…") if len(alt) > 120 else alt

    def _replace_fenced_pdflatex(self, md: str, out_dir: str) -> str:
        # Match fenced code blocks: ```pdflatex\n...\n```
        fence_re: Pattern[str] = re.compile(
            r"(^|\n)(?P<fence>```|~~~)\s*(?P<info>pdflatex\b[^\n]*)\n(?P<body>.*?)(?P=fence)\s*(?:\n|$)",
            re.S,
        )

        def repl(m: Match[str]) -> str:
            body: str = m.group("body").rstrip()
            h: str = self._hash(body, True)
            basename: str = "latex-" + h
            svg: str = self._render_to_svg(body, True, out_dir, basename)
            alt: str = self._sanitize_alt(body)
            return f'\n<img src="/{self.config["asset_subdir"]}/{os.path.basename(svg)}" alt="{alt}">\n'

        return fence_re.sub(repl, md)

    def _replace_display_math(self, md: str, out_dir: str) -> str:
        # Replace $$...$$ (multiline)
        disp_re: Pattern[str] = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$", re.S)

        def repl(m: Match[str]) -> str:
            body: str = m.group(1).strip()
            h: str = self._hash(body, True)
            basename: str = "latex-" + h
            svg: str = self._render_to_svg(body, True, out_dir, basename)
            alt: str = self._sanitize_alt(body)
            return f'<img src="/{self.config["asset_subdir"]}/{os.path.basename(svg)}" alt="{alt}" style="display:block;margin:0.4em 0;">'

        return disp_re.sub(repl, md)
