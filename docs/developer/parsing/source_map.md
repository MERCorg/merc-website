# Source Maps & Imports

A parser rarely runs over a single, self-contained string. A specification may
`%import` other files, an LSP parses in-memory buffers that were never saved,
and later stages register generated content that has no file behind it at all.
Every one of these needs spans that render correctly, uniformly, so a
diagnostic or an LSP go-to-definition query never has to know where a
[`Span`](https://mercorg.github.io/merc/merc_utilities/span/struct.Span.html) came
from. [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html) ([`merc_utilities`](https://mercorg.github.io/merc/merc_utilities/index.html)) is the shared foundation that makes this
possible.

## One shared, global offset space

A [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html) owns every file loaded into one compilation and assigns each a
disjoint slice of one shared, global byte-offset space: [`files`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html#structfield.files), a [`Vec`](https://doc.rust-lang.org/std/vec/struct.Vec.html) of [`SourceFile`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceFile.html),
sorted by [`base`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceFile.html#structfield.base) ascending, with no gaps. A [`Span`](https://mercorg.github.io/merc/merc_utilities/span/struct.Span.html)'s [`start`](https://mercorg.github.io/merc/merc_utilities/span/struct.Span.html#structfield.start)/[`end`](https://mercorg.github.io/merc/merc_utilities/span/struct.Span.html#structfield.end) are offsets
into this one space, not into any single file's own text — rendering a span
takes the [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html) and looks up which file an offset falls into, by binary
search over [`base`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceFile.html#structfield.base), before rendering the surrounding line. An offset past the
end of every loaded file resolves to the last one rather than panicking, so an
empty placeholder span still renders against *something*.

Three ways to register text, all returning a [`SourceId`](https://mercorg.github.io/merc/merc_utilities/source_map/type.SourceId.html) (a [`TagIndex`](https://mercorg.github.io/merc/merc_utilities/tagged_index/struct.TagIndex.html), cheap
to copy, meaningful only relative to the [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html) that produced it):

- **A real path**, read from disk.
- **Text with no on-disk file behind it** that still deserves file-accurate
  rendering: an LSP's in-memory buffer, an ad hoc expression string.
- **A virtual source** — generated content with no real file behind it *at
  all*, such as the system-defined declarations the type checker registers
  (see [The System-Defined
  Specification](../typechecking/system-specification.md#loading-system-defined-content-into-the-source-map)). The [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html) records
  which registrations are virtual, so a consumer (an LSP) can tell "jump to a
  file you can open and edit" apart from "jump to generated content" before
  deciding how to present it.

## `%import`: composing files before parsing

`%import "relative/path.mcrl2"` splices one file's declarations into another,
ahead of type checking. It uses mCRL2's own comment character, so a file that
uses it is still valid, ordinary mCRL2 to a tool that doesn't understand
imports at all.

Directives are found with a textual pre-scan — a line, once trimmed, of the
exact shape `%import "PATH"` — rather than anything grammar-level, so the scan
can run before the file it is scanning is known to parse at all. Parsing an
[`UntypedDataSpecification`](https://mercorg.github.io/merc/merc_syntax/struct.UntypedDataSpecification.html) (and its [`UntypedProcessSpecification`](https://mercorg.github.io/merc/merc_syntax/struct.UntypedProcessSpecification.html)/
[`UntypedStateFrmSpec`](https://mercorg.github.io/merc/merc_syntax/struct.UntypedStateFrmSpec.html) counterparts) then drives a [`Resolver`](https://mercorg.github.io/merc/merc_syntax/imports/struct.Resolver.html) that walks the
import graph depth-first:

- **[`merged`](https://mercorg.github.io/merc/merc_syntax/imports/struct.Resolver.html#structfield.merged)**, a [`HashMap`](https://doc.rust-lang.org/std/collections/struct.HashMap.html) from [`PathBuf`](https://doc.rust-lang.org/std/path/struct.PathBuf.html) to [`SourceId`](https://mercorg.github.io/merc/merc_utilities/source_map/type.SourceId.html) — every file already merged, by
  canonicalized path, so a diamond import (the same file reached from two
  different places in the tree) is merged once, not once per import site.
- **[`stack`](https://mercorg.github.io/merc/merc_syntax/imports/struct.Resolver.html#structfield.stack)**, a [`Vec`](https://doc.rust-lang.org/std/vec/struct.Vec.html) of [`PathBuf`](https://doc.rust-lang.org/std/path/struct.PathBuf.html) — the files currently being loaded, innermost
  last. A file reappearing *here* (rather than only in [`merged`](https://mercorg.github.io/merc/merc_syntax/imports/struct.Resolver.html#structfield.merged)) is a cycle,
  not a diamond, and is rejected as [`ImportError::Cycle`](https://mercorg.github.io/merc/merc_syntax/imports/enum.ImportError.html#variant.Cycle).

For each file, the [`Resolver`](https://mercorg.github.io/merc/merc_syntax/imports/struct.Resolver.html) registers its text into [`sources`](https://mercorg.github.io/merc/merc_syntax/imports/struct.Resolver.html#structfield.sources) — fixing its
base offset — *before* parsing it or descending into anything it imports. This
ordering is the precondition the rebasing step depends on: the file is
parsed at its own zero-based offsets, and only afterward is every span it
produced shifted into the slot already reserved for it. Parsing zero-based text
and shifting the result in one pass, rather than padding the text with `base`
leading bytes before handing it to pest, is both cheaper (no padding to
allocate and scan) and lets an already-parsed tree be reused by cloning it and
shifting the clone.

[`OffsetSpans`](https://mercorg.github.io/merc/merc_syntax/span_offset/trait.OffsetSpans.html) is a dedicated walk, one implementation per AST type, rather
than something [`Traverse`](https://mercorg.github.io/merc/merc_syntax/traverse/trait.Traverse.html) can do generically: [`Traverse`](https://mercorg.github.io/merc/merc_syntax/traverse/trait.Traverse.html)'s
recursion only ever descends into children of the *same* node type (a
[`SortExpression`](https://mercorg.github.io/merc/merc_syntax/type.SortExpression.html)'s children are other [`SortExpression`](https://mercorg.github.io/merc/merc_syntax/type.SortExpression.html)s), so it can't reach a
declaration's own span, an identifier's [`Spanned`](https://mercorg.github.io/merc/merc_syntax/spanned/struct.Spanned.html) name, or any other
differently-typed field that also carries one.

An `%import` failure — a directive whose target can't be resolved, a cycle,
or a file that fails to parse — is reported as a structured [`ImportError`](https://mercorg.github.io/merc/merc_syntax/imports/enum.ImportError.html)
([`Unresolved`](https://mercorg.github.io/merc/merc_syntax/imports/enum.ImportError.html#variant.Unresolved)/[`Cycle`](https://mercorg.github.io/merc/merc_syntax/imports/enum.ImportError.html#variant.Cycle)/[`Parse`](https://mercorg.github.io/merc/merc_syntax/imports/enum.ImportError.html#variant.Parse)) rather than a formatted string, keeping the
original [`MercError`](https://mercorg.github.io/merc/merc_utilities/error/struct.MercError.html) recoverable by downcasting, however deeply nested it is
behind [`Unresolved`](https://mercorg.github.io/merc/merc_syntax/imports/enum.ImportError.html#variant.Unresolved) layers. This matters for a caller with access
to the [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html) (an LSP): an [`ImportError`](https://mercorg.github.io/merc/merc_syntax/imports/enum.ImportError.html) carries the failing directive's
own quoted-path span, and can recover the underlying parser error —
line/column, expected tokens — through any number of nested [`Unresolved`](https://mercorg.github.io/merc/merc_syntax/imports/enum.ImportError.html#variant.Unresolved)
wrappers, so a precise diagnostic can be built without re-parsing rendered
error text.
