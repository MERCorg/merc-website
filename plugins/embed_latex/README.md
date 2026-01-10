# Overview

This plugin requires a working LaTeX installation with `pdflatex` and `pdf2svg`
available in the system `PATH`.

Configuration:
 - 'dvisvgm_cmd': Command to convert DVI to SVG. Default: `dvisvgm --no-fonts`
 - 'pdflatex_cmd': Command to compile LaTeX to DVI. Default: `pdflatex -interaction=nonstopmode -halt-on-error`
 - 'asset_subdir': Subdirectory in the site output directory to store generated images