# Source Maps, Imports & Virtual Templates

Type checking rarely runs over a single, self-contained string. A
specification may `%import` other files, and the type checker itself splices
in generated content — the Appendix-B builtins and the instantiated container
templates described in [The System-Defined
Specification](system-specification.md). All three categories — the user's
own text, an imported file, and generated content with no file behind it at
all — need spans that render correctly, uniformly, so a diagnostic or an
LSP go-to-definition query never has to know which category a [`Span`](https://mercorg.github.io/merc/merc_utilities/span/struct.Span.html) came
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
  all*, such as the system-defined declarations below. The [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html) records
  which registrations are virtual, so a consumer (an LSP) can tell "jump to a
  file you can open and edit" apart from "jump to generated content" before
  deciding how to present it.

Because all three share one offset space, building a [`DataSpecification`](https://mercorg.github.io/merc/merc_typecheck/data_specification/struct.DataSpecification.html) takes
a `&mut` [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html) rather than creating its own: pass the same [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html) a
file was parsed (and `%import`-resolved) against, so the generated
system-defined content it registers lands in that same space. There is also a
convenience wrapper over a throwaway [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html), fine for a caller that never
needs to render a span afterward (most tests), wrong for a caller with an
on-disk file that might import others or that needs to point a diagnostic into
system-defined content.

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
ordering is the precondition every rebasing step below depends on: the file is
parsed at its own zero-based offsets, and only afterward is every span it
produced shifted into the slot already reserved for it. Parsing zero-based text
and shifting the result in one pass, rather than padding the text with `base`
leading bytes before handing it to pest, is both cheaper (no padding to
allocate and scan) and lets an already-parsed tree be reused by cloning it and
shifting the clone — exactly what the bundled templates below do.

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

## Virtual sources: giving generated content a real span

The bundled `spec/*.mcrl2` templates (`bool.mcrl2`, `list.mcrl2`, …) are
parsed twice, for two different purposes, and only one of the two registers
into a [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html) at all:

- **A bare parse** — no [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html) involved, spans meaningless outside the
  bare parsed AST itself. This is what [`CONTAINER_TEMPLATES`](https://mercorg.github.io/merc/merc_typecheck/signature/standard_sorts/static.CONTAINER_TEMPLATES.html) and
  [`BUILTIN_SCHEME_TEMPLATE`](https://mercorg.github.io/merc/merc_typecheck/signature/standard_sorts/static.BUILTIN_SCHEME_TEMPLATE.html) are built from: the source
  [`Signature::schemes`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.schemes) (see [polymorphism](polymorphism.md)) draws its [`PolySortScheme`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.PolySortScheme.html)s from.
  Nothing built this way is ever rendered, so registering it would be pure
  overhead.
- **A registered parse** — the same bundled text goes into [`sources`](https://mercorg.github.io/merc/merc_syntax/imports/struct.Resolver.html#structfield.sources) under a
  synthetic name like `<builtin>/list.mcrl2` or `<builtin>/nat.mcrl2`, as a
  virtual source, and its spans are rebased into that registration's base
  offset. It reuses the already-parsed bare AST — cloned, then shifted —
  instead of parsing the same text a second time. `basics` is built this way
  (part of [`DataSpecification`](https://mercorg.github.io/merc/merc_typecheck/data_specification/struct.DataSpecification.html)'s own [`system`](https://mercorg.github.io/merc/merc_typecheck/data_specification/struct.DataSpecification.html#structfield.system) field, built eagerly), and so is
  the per-concrete-sort content instantiated at [lowering
  time](system-specification.md#materializing-ground-content-at-lowering-time)
  for the container/function-update/comparison operations that only ever exist
  as generated output, never as part of `system` itself — either way, the
  content needs a span that renders somewhere real.

So the same five container templates (`list`, `set`, `fset`, `bag`, `fbag`)
exist in two independent forms at runtime: one bare copy feeding the
polymorphic scheme table inference searches, and one registered,
per-instantiation copy (`<builtin>/list.mcrl2` for `List(Nat)`, another
registration for `List(D)`, …) feeding the generated content lowering
produces. Confusing the two would be a category error — the bare copy's spans
are not meaningful against any [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html) at all. Function-update has no
bundled template file at all, in either form — its scheme and equations are
generated programmatically, per arity, the first time that arity is
encountered — see [Type Variables & Polymorphic Schemes](polymorphism.md).

## Real declaration spans for system-defined symbols

Because the system-defined declarations above now carry real, renderable
spans, the type checker can answer a go-to-definition query for a symbol the
user never declared — `@c0`, a struct's desugared `is_c1`/`pr1`, and the rest
of `basics`. A [`HashMap`](https://doc.rust-lang.org/std/collections/struct.HashMap.html) from `(name, `[`ResolvedSortId`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/type.ResolvedSortId.html)`)` to [`Span`](https://mercorg.github.io/merc/merc_utilities/span/struct.Span.html) on the checking
context ([`system_symbol_spans`](https://mercorg.github.io/merc/merc_typecheck/inference/context/struct.TypeCheckContext.html#structfield.system_symbol_spans)) is populated as a side effect of resolving `system`'s own signature
([Checking `system`: basics and desugared
structs](system-specification.md#checking-system-basics-and-desugared-structs)):
as that pass walks `system`'s own constructor/mapping declarations to resolve
their sorts, it also records each `(name, resolved sort)` pair's declaration
span, taken directly from the virtual source it was parsed from.

A container/function-update/comparison operator (`in`, `head`, `==`, …) is
not covered by this table at all: it is looked up as a
[scheme](polymorphism.md), never a concrete `system` declaration, and that pass
only ever walks `system`'s own declarations. Name resolution still degrades
gracefully — a missed lookup reports [`ResolvedName::SystemDefined { name,
declaration: None }`](https://mercorg.github.io/merc/merc_typecheck/typing_info/enum.ResolvedName.html#variant.SystemDefined) rather than panicking — but a go-to-definition query for
one of these names currently has no span to offer, only the name itself.

Building a [`TypingInfo`](https://mercorg.github.io/merc/merc_typecheck/typing_info/struct.TypingInfo.html) ([LSP support](typing-info.md#lsp-support)) consults this table as a
fallback: a [`NameTarget::Op`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.NameTarget.html#variant.Op) occurrence that isn't one of the *user*
specification's own constructors or mappings (the [`DeclarationIndex`](https://mercorg.github.io/merc/merc_typecheck/typing_info/struct.DeclarationIndex.html), built
from the user's own declaration lists) is looked up in the system-symbol table
instead, and reported as [`ResolvedName::SystemDefined { name, declaration }`](https://mercorg.github.io/merc/merc_typecheck/typing_info/enum.ResolvedName.html#variant.SystemDefined).
Before this
table existed, a reference to a built-in symbol had no declaration span to
offer at all; now hovering one resolves to a real location inside the
relevant `<builtin>/*.mcrl2` virtual document.

This is a different table from [`Signature::schemes`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.schemes)
([polymorphism.md](polymorphism.md)) on purpose: `schemes` exists purely to
give Phase-3 inference an overload set to search, built from the *bare*,
unregistered parse, and carries no span at all. The system-symbol table exists
purely to answer a go-to-definition query, built from the *registered* parse.
A container or comparison operator's occurrence is typed through the first
table and, once resolved to a concrete overload, can still have its
declaration looked up through the second — the two never need to agree on
representation, only on which concrete `(name, sort)` pair they each end up
describing.
