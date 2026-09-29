```math_preamble

\usepackage{tikz}
\usetikzlibrary{babel}
```
# Overview

The [`merc_typecheck`](https://mercorg.github.io/merc/merc_typecheck/index.html) crate type checks mCRL2 data specifications, following the
definitions in *Modeling and Analysis of Communicating Systems* (Groote &
Mousavi, MIT Press 2014). A type checker turns the loosely-structured syntax
tree produced by the parser into a fully typed specification: it resolves every
name, decides the sort of every expression, chooses between overloaded
operators, and inserts the implicit coercions that the surface language leaves
out (such as reading a natural number where a real number is expected).

The entry point builds a [`DataSpecification`](https://mercorg.github.io/merc/merc_typecheck/struct.DataSpecification.html) from the untyped [`merc_syntax`](https://mercorg.github.io/merc/merc_syntax/index.html) AST
produced by the parser. Rather than performing all of this in one recursive
traversal, we split type checking into a **pipeline of phases**, each with a
well-defined input and output, see the phases below.

During type checking sorts are interned indices into a standalone arena, so
equality is a single integer comparison and typings live in compact side tables
keyed by expression id. Only the final lowering phase produces the maximally
shared aterm representation that the rest of merc ([`merc_sabre`](https://mercorg.github.io/merc/merc_sabre/index.html), [`merc_explore`](https://mercorg.github.io/merc/merc_explore/index.html))
consumes.

## Contents

This part of the documentation is split one page per pass, plus one page per
specification kind built on top of them:

 - **[Phase 0: Sort & Name Resolution](name-resolution.md)** — Sort name
   resolution, alias-cycle checks, and canonicalization.
 - **[Phase 1: Desugaring](desugaring.md)** — Structured sorts to
   constructors/recognisers/projections, built-in operators to applications.
 - **[Phase 2: Signature & Well-Typedness](signature.md)** — The $(S, C, M)$
   triple and well-typedness conditions.
 - **[Phase 3: The System-Defined Specification](system-specification.md)** —
   Appendix B's standard data types, why they're checked apart from the
   user's own declarations, how a system equation is type checked against a
   deliberately narrower view of the polymorphic built-ins, and how it is
   loaded into the shared source map.
 - **[Phase 4: Type Variables & Polymorphic Schemes](polymorphism.md)** — the
   `type_var` block, [`ResolvedSort::TypeVar`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.TypeVar), and how a scheme like
   `in: S # List(S) -> Bool` is resolved once and instantiated fresh at
   every use site.
 - **[Phase 5: Sort Inference](sort-inference.md)** — The sort lattice,
   constraint generation, unification with subtyping, and the ranked
   backtracking search — the heart of the crate.
     - **[Inference Internals](inference/index.md)** — the implementation
       behind that page, function by function: the `Unifier`'s arena and
       union-find split, and the constraint generator/solver's pseudocode.

**Specification kinds built on the pipeline above:**

 - **[Specification Type Checking](../specification/index.md)** — how
   [`ProcessSpecification`](https://mercorg.github.io/merc/merc_typecheck/process/process_specification/struct.ProcessSpecification.html), [`PbesSpecification`](https://mercorg.github.io/merc/merc_typecheck/pbes/pbes_specification/struct.PbesSpecification.html), and [`PresSpecification`](https://mercorg.github.io/merc/merc_typecheck/pres/pres_specification/struct.PresSpecification.html) each
   build on the data checker, collecting their own declarations and then
   type checking every expression.
 - **[Span-Keyed Typing Info (LSP Support)](typing-info.md)** — the [`TypingInfo`](https://mercorg.github.io/merc/merc_typecheck/typing_info/struct.TypingInfo.html) API
   that exposes typing facts by source [`Span`](https://mercorg.github.io/merc/merc_utilities/span/struct.Span.html) for editor tooling.
