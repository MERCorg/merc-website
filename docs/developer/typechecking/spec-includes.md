# Source Maps, Imports & Virtual Templates

Type checking rarely runs over a single, self-contained string. A
specification may `%import` other files, and the type checker itself splices
in generated content — the Appendix-B builtins and the instantiated container
templates described in [The System-Defined
Specification](system-specification.md). All three categories — the user's
own text, an imported file, and generated content with no file behind it at
all — need spans that render correctly, uniformly, so a diagnostic or an
LSP go-to-definition query never has to know which category a `Span` came
from. `SourceMap` (`merc_utilities`) is the shared foundation that makes this
possible.

## One shared, global offset space

A `SourceMap` owns every file loaded into one compilation and assigns each a
disjoint slice of one shared, global byte-offset space: `files: Vec<SourceFile>`,
sorted by `base` ascending, with no gaps. A `Span`'s `start`/`end` are offsets
into this one space, not into any single file's own text — `Span::render`
takes the `SourceMap` and looks up which file an offset falls into
(`SourceMap::lookup`, a binary search over `base`) before rendering the
surrounding line. An offset past the end of every loaded file resolves to the
last one rather than panicking, so a synthetic span (`Span::default`) still
renders against *something*.

Three ways to register text, all returning a `SourceId` (a `TagIndex`, cheap
to copy, meaningful only relative to the `SourceMap` that produced it):

- **`load_file`** — reads a real path from disk.
- **`add_text`** — text with no on-disk file behind it that still deserves
  file-accurate rendering: an LSP's in-memory buffer, an ad hoc expression
  string.
- **`add_virtual`** — generated content with no real file behind it *at all*,
  such as the system-defined declarations below. `SourceMap::is_virtual`
  records which is which, so a consumer (an LSP) can tell "jump to a file you
  can open and edit" apart from "jump to generated content" before deciding
  how to present it.

Because all three share one offset space, `DataSpecification::from_untyped_with`
takes a `sources: &mut SourceMap` parameter rather than creating its own: pass
the same `SourceMap` a file was parsed (and `%import`-resolved) against, so
the generated system-defined content it registers lands in that same space.
`DataSpecification::from_untyped` is a convenience wrapper over a throwaway
`SourceMap`, fine for a caller that never needs to render a span afterward
(most tests), wrong for a caller with an on-disk file that might import
others or that needs to point a diagnostic into system-defined content.

## `%import`: composing files before parsing

`%import "relative/path.mcrl2"` splices one file's declarations into another,
ahead of type checking. It uses mCRL2's own comment character, so a file that
uses it is still valid, ordinary mCRL2 to a tool that doesn't understand
imports at all.

`scan_imports` finds directives with a textual pre-scan — a line, once
trimmed, of the exact shape `%import "PATH"` — rather than anything
grammar-level, so it can run before the file it's scanning is known to parse
at all. `UntypedDataSpecification::parse_with_imports` (and the
`UntypedProcessSpecification`/`UntypedStateFrmSpec` counterparts) then drive a
`Resolver` that walks the import graph depth-first:

- **`merged: HashMap<PathBuf, SourceId>`** — every file already merged, by
  canonicalized path, so a diamond import (the same file reached from two
  different places in the tree) is merged once, not once per import site.
- **`stack: Vec<PathBuf>`** — the files currently being loaded, innermost
  last. A file reappearing *here* (rather than only in `merged`) is a cycle,
  not a diamond, and is rejected as `ImportError::Cycle`.

For each file, `Resolver::load_with_text` registers its text into `sources`
— fixing its base offset — *before* parsing it or descending into anything
it imports. This ordering is the precondition every rebasing step below
depends on: `T::parse_own_text` parses the file at its own zero-based
offsets, and only afterward does `file_spec.offset_spans(base)` shift every
span it produced into the slot already reserved for it. Parsing zero-based
text and shifting the result in one pass, rather than padding the text with
`base` leading bytes before handing it to pest, is both cheaper (no padding
to allocate and scan) and lets an already-parsed tree be reused by cloning it
and shifting the clone — exactly what `register_bare_template` below does for
the container templates.

`OffsetSpans::offset_spans` is a dedicated walk, one implementation per AST
type, rather than something `Traverse` can do generically: `Traverse`'s
recursion only ever descends into children of the *same* node type (a
`SortExpression`'s children are other `SortExpression`s), so it can't reach a
declaration's own span, an identifier's `Spanned` name, or any other
differently-typed field that also carries one.

An `%import` failure — a directive whose target can't be resolved, a cycle,
or a file that fails to parse — is reported as a structured `ImportError`
(`Unresolved`/`Cycle`/`Parse`) rather than a formatted string, keeping the
original `MercError` recoverable via `MercError::downcast_ref` however deeply
nested it is behind `Unresolved` layers. This matters for a caller with
access to the `SourceMap` (an LSP): `ImportError::span()` gives the failing
directive's own quoted-path span, and `ImportError::pest_error()` recovers
the underlying parser error — line/column, expected tokens — through any
number of nested `Unresolved` wrappers, so a precise diagnostic can be built
without re-parsing rendered error text.

## Virtual sources: giving generated content a real span

The bundled `spec/*.mcrl2` templates (`bool.mcrl2`, `list.mcrl2`, …) are
parsed twice, for two different purposes, and only one of the two registers
into a `SourceMap` at all:

- **`parse_template_bare`** — no `SourceMap` involved, spans meaningless
  outside the bare parsed AST itself. This is what `CONTAINER_TEMPLATES` and
  `BUILTIN_SCHEME_TEMPLATE` are built from: the source
  [`Signature::schemes`](polymorphism.md) draws its `PolySortScheme`s from.
  Nothing built this way is ever rendered, so registering it would be pure
  overhead.
- **`parse_template`/`register_bare_template`** — registers the same bundled
  text into `sources` under a synthetic name like `<builtin>/list.mcrl2` or
  `<builtin>/nat.mcrl2` (via `add_virtual`), then rebases its spans into that
  registration's base offset. `register_bare_template` specifically reuses
  the already-parsed bare AST (`template.clone()` then `offset_spans`)
  instead of parsing the same text a second time. This is what
  `build_system_defined_specification` instantiates per concrete sort — the
  content that actually joins a `DataSpecification`'s `system` field, and so
  needs a span that renders somewhere real.

So the same six container templates exist in two independent forms at
runtime: one bare copy feeding the polymorphic scheme table inference
searches, and one registered, per-instantiation copy (`<builtin>/list.mcrl2`
for `List(Nat)`, another registration for `List(D)`, …) feeding the system
specification's own declarations and equations. Confusing the two would be a
category error — the bare copy's spans are not meaningful against any
`SourceMap` at all.

## Real declaration spans for system-defined symbols

Because the system-defined declarations above now carry real, renderable
spans, the type checker can answer a go-to-definition query for a symbol the
user never declared — `in`, `head`, `@c0`, and the rest of Appendix B.
`TypeCheckContext::system_symbol_spans: HashMap<(String, ResolvedSortId),
Span>` is populated as a side effect of `resolve_system_signature` and
`resolve_system_signature_full` ([Name resolution inside a system
equation](system-specification.md#name-resolution-inside-a-system-equation)):
as each walks a group's own constructor/mapping declarations to resolve
their sorts, it also records that `(name, resolved sort)` pair's declaration
span, taken directly from the virtual source it was parsed from.

[`typing_info::build`](typing-info.md#lsp-support)'s `resolved_name` helper
consults this table as a fallback: a `NameTarget::Op` occurrence that isn't
one of the *user* specification's own constructors or mappings
(`DeclarationIndex::constructors`/`mappings`, built from the user's own
declaration lists) is looked up in `system_symbol_spans` instead, and
reported as `ResolvedName::SystemDefined { name, declaration }`. Before this
table existed, a reference to a built-in symbol had no declaration span to
offer at all; now hovering one resolves to a real location inside the
relevant `<builtin>/*.mcrl2` virtual document.

This is a different table from `Signature::schemes`
([polymorphism.md](polymorphism.md)) on purpose: `schemes` exists purely to
give Phase-3 inference an overload set to search, built from the *bare*,
unregistered parse, and carries no span at all. `system_symbol_spans` exists
purely to answer a go-to-definition query, built from the *registered* parse.
A container or comparison operator's occurrence is typed through the first
table and, once resolved to a concrete overload, can still have its
declaration looked up through the second — the two never need to agree on
representation, only on which concrete `(name, sort)` pair they each end up
describing.
