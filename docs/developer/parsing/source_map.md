# Source maps and imports

A specification may `%import` other files, a language server parses in-memory
buffers that were never saved, and later stages register generated content
without a file behind it. Every span produced from any of these must render
correctly, without the consumer knowing where it came from. This page defines the
shared offset space that makes this possible (Definition 5) and how `%import`
composes files (Definition 6). The offset space is
`SourceMap`
in [`merc_utilities`](https://mercorg.github.io/merc/merc_utilities/index.html);
imports are resolved in
[`merc_syntax`](https://mercorg.github.io/merc/merc_syntax/index.html).

## One shared offset space

**Definition 5 (source map).** A *source map* is a sequence of sources
$f_1, \ldots, f_n$, each with a text $t_i$ and a *base offset* $b_i$, where
$b_1 = 0$ and $b_{i+1} = b_i + |t_i|$. Every span is a pair of offsets into this
one space. An offset $o$ belongs to the source $f_i$ with $b_i \le o < b_{i+1}$,
and to the last source if it lies past the end of all of them.

So a span does not name its file: rendering it looks up its source by binary
search over the base offsets, and the offset within that source is $o - b_i$.
The last rule lets an empty placeholder span still render against some source.

A source is registered in one of three ways, each returning a
`SourceId`
that is meaningful only for the source map that produced it:

- a file read from disk;
- text without a file, such as an editor's unsaved buffer or an expression
  string;
- a *virtual* source: generated content without any file, such as the
  [system-defined declarations](../typechecking/system-specification.md#source-locations)
  of the type checker. The source map records which sources are virtual, so a
  language server can tell a file the user can open apart from generated
  content.

## `%import`

`%import "relative/path.mcrl2"` splices the declarations of one file into
another, before type checking. It starts with mCRL2's comment character, so a
file that uses it is still an ordinary mCRL2 file to a tool that does not know
about imports. Directives are found by a textual scan for lines that, once
trimmed, have exactly the shape `%import "PATH"`, so the scan works before the
file is known to parse.

**Definition 6 (import resolution).** Resolving the imports of a root file walks
the graph of `%import` directives depth first. It keeps the set of files already
merged and the stack of files currently being loaded, both by canonical path.
For every directive whose target

- is on the stack, resolution fails with an import *cycle*;
- is already merged, it does nothing: a file reached along two paths (a
  *diamond*) is merged once;
- is neither, it registers the target in the source map, parses it, resolves the
  target's own imports, and merges the target's declarations ahead of those
  already collected.

The result records, for every directive, the file it resolved to, as an
`ImportGraph`.

A file is registered, fixing its base offset, *before* it is parsed or any of its
imports is visited. It is then parsed at its own offsets starting at zero, and
every span of the resulting tree is shifted by its base offset, by the trait
`OffsetSpans`.
Shifting the parsed tree is cheaper than padding the text with $b_i$ bytes before
parsing it, and it lets an already parsed tree be reused by shifting a copy.
`OffsetSpans` is a separate traversal per syntax type, because the generic
traversal of the syntax tree only visits children of the same type, and so
cannot reach, for example, the span of a declaration's identifier.

A failure is an
`ImportError`:
an unresolved directive (a missing or unreadable file, or one whose own import
fails, one level further down), a cycle, or a file that does not parse. It keeps
the underlying error structured rather than rendered into a string, and carries
the span of the failing directive, so a language server can recover the
parser's location and message through any number of nested unresolved
directives and build a precise diagnostic.
