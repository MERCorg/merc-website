# LSP Support

Everything in the [data specification](data-specification.md) and [process
specification](process-specification.md) pipelines tracks sorts internally by
`ExprId`, an index assigned over the *lowered* expression tree — it can
contain nodes with no counterpart in the original, unlowered syntax a caller
parsed (the desugared `Id("+")` of `x + y`, for instance), so an external
caller such as an editor integration cannot safely reconstruct it by
re-walking the original tree after the fact.

`DataSpecification::typing_info` (whole specification) and
`DataSpecification::equation_typing_info` (one equation) instead expose a
`TypingInfo`: one `TypedNode` per checked expression node — its source `Span`,
its inferred sort (reconstructed as a `SortExpression` for display), and what
its identifier resolved to (`ResolvedName`: a variable, a user `Constructor`/
`Mapping` with its declaration span when it has one, a system-defined
Appendix-B symbol, or a polymorphic builtin) — keyed by that `Span` rather than
any internal id. `TypingInfo::at_offset` answers the hover/go-to-definition
query directly: the most specific node whose span contains a byte offset,
breaking span ties (a synthesized node inherits its surface expression's span,
so e.g. `x + y`'s synthesized `Id("+")` and its `Application` node can share
one span) in favor of the later, more specific node in generation order.
`DataSpecification::typecheck_expression_with_typing` gives the same
`TypingInfo` for a single standalone expression checked outside any
specification. Note that a `TypedNode`'s reconstructed *sort* always carries
`Span::default` — a resolved sort has no reliable source location of its own,
since name resolution and alias normalization both discard or relocate a
sort's original span — so this API can't answer sort go-to-definition from
`TypedNode::sort` alone; use the `Def` sort's carried `DefId` instead.

This is groundwork for LSP-style tooling (hover, go-to-definition) rather than
a consumer of it — no editor integration exists in this repository itself, but
an experimental language server built on it lives at
[MERCorg/merc-lsp](https://github.com/MERCorg/merc-lsp).
