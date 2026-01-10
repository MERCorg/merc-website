import hashlib
import os
import re
import shlex
import subprocess
import tempfile
from typing import Any, Match, Pattern

from mkdocs.plugins import BasePlugin
from mkdocs.config import config_options


class EmbedLatexPlugin(BasePlugin):
    """
    MkDocs plugin: render LaTeX math (inline $...$, display $$...$$ and fenced blocks with info 'pdflatex')
    to SVG images using pdflatex + dvisvgm.
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
        ("temp_dir", config_options.Type(str, default="") ),
    )

    def on_page_markdown(
        self, markdown: str, /, *, page: Any, config: Any, files: Any
    ) -> str:
        """
        Override of the BasePlugin method to process the page markdown to replace LaTeX math with SVG images.
        """
        
        site_assets_dir: str = os.path.join(config["site_dir"], self.config["asset_subdir"])
        os.makedirs(site_assets_dir, exist_ok=True)

        # First replace fenced code blocks with info 'pdflatex' -> display math images
        markdown = self._replace_fenced_pdflatex(markdown, site_assets_dir)

        # Then handle $$...$$ display math
        markdown = self._replace_display_math(markdown, site_assets_dir)

        return markdown

    def _hash(self, tex: str) -> str:
        h = hashlib.sha1()
        h.update(b"pdflatex_v1")
        h.update(tex.encode("utf-8"))
        return h.hexdigest()

    def _render_to_svg(self, tex_body: str, out_dir: str, basename: str) -> str:
        svg_path: str = os.path.join(out_dir, basename + ".svg")
        if os.path.exists(svg_path):
            # Skip rendering if SVG already exists, since we hash the input.
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
        tex: str = env % tex_body

        with tempfile.TemporaryDirectory(dir=self.config["temp_dir"] or None, delete=False) as td:
            tex_file: str = os.path.join(td, basename + ".tex")
            with open(tex_file, "w", encoding="utf-8") as f:
                f.write(tex)

            pdflatex_cmd = shlex.split(self.config["pdflatex_cmd"]) + [
                "-output-directory",
                td,
                tex_file,
            ]
            proc = subprocess.run(
                pdflatex_cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            if proc.returncode != 0:
                print(f"latex {tex_file} pdflatex error: {proc.stdout.decode('utf-8')}")
                
                # on error, write a simple SVG placeholder
                with open(svg_path, "w", encoding="utf-8") as f:
                    f.write(
                        '<svg xmlns="http://www.w3.org/2000/svg"><text y="14">LaTeX error</text></svg>'
                    )
                return svg_path

            pdf_file: str = os.path.join(td, basename + ".pdf")

            # Run dvisvgm to convert PDF to SVG
            dvisvgm_cmd = shlex.split(self.config["dvisvgm_cmd"]) + [
                pdf_file,
                "-o",
                svg_path,
            ]
            proc = subprocess.run(
                dvisvgm_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            if proc.returncode != 0:
                print(f"pdf {pdf_file} dvisvgm error: {proc.stdout.decode('utf-8')}")

                with open(svg_path, "w", encoding="utf-8") as f:
                    f.write(
                        '<svg xmlns="http://www.w3.org/2000/svg"><text y="14">Conversion error</text></svg>'
                    )

            return svg_path

    def _sanitize_alt(self, text: str) -> str:
        """Sanitize alt text for the img alt tag."""
        alt: str = text.replace('"', "'")
        alt = re.sub(r"\s+", " ", alt)
        return (alt[:120] + "…") if len(alt) > 120 else alt

    def _replace_fenced_pdflatex(self, md: str, out_dir: str) -> str:
        """Replace fenced code blocks: ```pdflatex\n...\n```"""
        fence_re: Pattern[str] = re.compile(
            r"(^|\n)(?P<fence>```|~~~)\s*(?P<info>pdflatex\b[^\n]*)\n(?P<body>.*?)(?P=fence)\s*(?:\n|$)",
            re.S,
        )

        def repl(m: Match[str]) -> str:
            body: str = m.group("body").rstrip()
            h: str = self._hash(body)
            basename: str = "latex-" + h
            svg: str = self._render_to_svg(body, out_dir, basename)
            alt: str = self._sanitize_alt(body)
            return f'\n<img src="/{self.config["asset_subdir"]}/{os.path.basename(svg)}" alt="{alt}">\n'

        return fence_re.sub(repl, md)

    def _replace_display_math(self, md: str, out_dir: str) -> str:
        """Replace $$...$$ (multiline)"""
        disp_re: Pattern[str] = re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$", re.S)

        def repl(m: Match[str]) -> str:
            body: str = m.group(1).strip()
            h: str = self._hash(body)
            basename: str = "latex-" + h
            svg: str = self._render_to_svg(body, out_dir, basename)
            alt: str = self._sanitize_alt(body)
            return f'<img src="/{self.config["asset_subdir"]}/{os.path.basename(svg)}" alt="{alt}" style="display:block;margin:0.4em 0;">'

        return disp_re.sub(repl, md)
