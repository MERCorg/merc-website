```math_preamble

\usepackage{tikz}
\usetikzlibrary{babel}
```
# Overview

The `merc_typecheck` crate type checks mCRL2 data specifications, following the
definitions in *Modeling and Analysis of Communicating Systems* (Groote &
Mousavi, MIT Press 2014). A type checker turns the loosely-structured syntax
tree produced by the parser into a fully typed specification: it resolves every
name, decides the sort of every expression, chooses between overloaded
operators, and inserts the implicit coercions that the surface language leaves
out (such as reading a natural number where a real number is expected).

Rather than performing all of this in one recursive traversal, merc splits type
checking into a **pipeline of phases**, each with a well-defined input and
output. The architecture is *query-based* in the style of the Rust compiler:
each derived fact — the signature of a specification, the sort denoted by a
declaration, the typing of an equation — is a memoized query on a shared
`TypeckContext`, so phases pull their dependencies lazily and every fact is
computed at most once. Cyclic definitions (a sort alias that refers to itself,
say) are detected through the memoization table's lock state instead of running
away into unbounded recursion.

!!! question "Is the per-query memoization worth its complexity?"
    Not a settled question. Several passes already walk the full AST to
    perform other syntactic operations, so it is not yet clear how much the
    per-query memoization saves over simply recomputing facts during one of
    those existing traversals, versus what it costs in bookkeeping.

The entry point is `DataSpecification::from_untyped`, which takes the untyped
`merc_syntax` AST produced by the parser and runs the phases below.

## Overview

<div align="center">

```math

\begin{tikzpicture}[
  every node/.style={font=\small},
  lbl/.style={font=\scriptsize, align=left}
]

\node[draw, rounded corners=6pt, minimum width=7.4cm, minimum height=1.1cm, align=center] (untyped) at (0,0) {UntypedDataSpecification \\ \scriptsize(merc\_syntax AST)};

\node[draw, rounded corners=6pt, minimum width=7.4cm, minimum height=1.1cm, align=center] (typed) at (0,-6.4) {Typed specification + sort assignment \\ \scriptsize(ExprId $\to$ ResolvedSort)};

\node[draw, rounded corners=6pt, minimum width=7.4cm, minimum height=1.1cm, align=center] (lowered) at (0,-9.8) {merc\_data::Mcrl2DataSpecification \\ \scriptsize(aterm, fully typed)};

\draw[->, thick] (untyped) -- (typed) node[midway, right, lbl, xshift=3mm] {
  Phase 0 -- sort layer: flatten, name resolution,\\
  \hspace{2mm} alias checks, normalization\\
  Phase 1 -- desugaring and operator lowering\\
  Phase 2 -- signature $(S, C, M)$ + well-typedness checks;\\
  \hspace{2mm} sort resolution onto the interned lattice\\
  Phase 3 -- constraint-based sort inference\\
  \hspace{2mm} (per equation, memoized)
};

\draw[->, thick] (typed) -- (lowered) node[midway, right, lbl, xshift=3mm] {Phase 4 -- lowering};

\end{tikzpicture}
```

</div>

The guiding idea is a **split representation**. During type checking, sorts are
*not* aterms: they are interned indices into a standalone arena, so equality is
a single integer comparison and typings live in compact side tables keyed by
expression id. This keeps the checker independent of the aterm term pool —
faster, testable in isolation, and free of garbage-collection concerns while a
fixed-point search runs. Only the final lowering phase produces the maximally
shared aterm representation that the rest of merc (`merc_sabre`,
`merc_explore`) consumes.

## Contents

This part of the documentation is split into three pages:

 - **[Data Specification Type Checking](data-specification.md)** — the core
   pipeline sketched above: the sort layer, desugaring, the signature and the
   system-defined specification, the sort lattice, constraint-based sort
   inference, and lowering back to aterms.
 - **[Process Specification Type Checking](process-specification.md)** — how
   `ProcessSpecification` builds on the data checker, including the
   `.`/`+` grammar-ambiguity reparse pass it runs first.
 - **[Span-Keyed Typing Info (LSP Support)](lsp.md)** — the `TypingInfo` API
   that exposes typing facts by source `Span` for editor tooling.
