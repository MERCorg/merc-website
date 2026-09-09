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
  stage/.style={draw, rounded corners=6pt, minimum width=7.4cm, minimum height=1.1cm, align=center},
  phase/.style={draw, dashed, rounded corners=4pt, minimum width=6.8cm, minimum height=0.9cm, align=center, font=\scriptsize}
]

\node[stage] (untyped) at (0,0) {UntypedDataSpecification \\ \scriptsize(merc\_syntax AST)};

\node[phase] (phase0) at (0,-1.9) {Phase 0 -- sort layer\\ flatten, name resolution, alias checks, normalization};

\node[phase] (phase1) at (0,-3.4) {Phase 1 -- desugaring and operator lowering};

\node[phase] (phase2) at (0,-4.9) {Phase 2 -- signature $(S, C, M)$ + well-typedness checks\\ sort resolution onto the interned lattice};

\node[phase] (phase3) at (0,-6.4) {Phase 3 -- constraint-based sort inference\\ (per equation, memoized)};

\node[stage] (typed) at (0,-8.2) {Typed specification + sort assignment \\ \scriptsize(ExprId $\to$ ResolvedSort)};

\node[phase] (phase4) at (0,-9.7) {Phase 4 -- lowering};

\node[stage] (lowered) at (0,-11.1) {merc\_data::Mcrl2DataSpecification \\ \scriptsize(aterm, fully typed)};

\draw[->, thick] (untyped) -- (phase0);
\draw[->, thick] (phase0) -- (phase1);
\draw[->, thick] (phase1) -- (phase2);
\draw[->, thick] (phase2) -- (phase3);
\draw[->, thick] (phase3) -- (typed);
\draw[->, thick] (typed) -- (phase4);
\draw[->, thick] (phase4) -- (lowered);

\end{tikzpicture}
```

</div>

The guiding idea is a **split representation**. During type checking sorts are
interned indices into a standalone arena, so equality is a single integer
comparison and typings live in compact side tables keyed by expression id. Only
the final lowering phase produces the maximally shared aterm representation that
the rest of merc (`merc_sabre`, `merc_explore`) consumes.

## Contents

This part of the documentation is split one page per pass, plus one page per
specification kind built on top of them:

 - **[Sort & Name Resolution](name-resolution.md)** — Phase 0: sort name
   resolution, alias-cycle checks, and canonicalization.
 - **[Desugaring](desugaring.md)** — Phase 1: structured sorts to
   constructors/recognisers/projections, built-in operators to applications.
 - **[Signature & Well-Typedness](signature.md)** — Phase 2: the
   $(S, C, M)$ triple and Definition 15.1.7's well-typedness conditions.
 - **[The System-Defined Specification](system-specification.md)** —
   Appendix B's standard data types, why they're checked apart from the
   user's own declarations, and how a system equation is type checked
   against a deliberately narrower, group-scoped view of the polymorphic
   built-ins.
 - **[Type Variables & Polymorphic Schemes](polymorphism.md)** — the
   `type_var` block, `ResolvedSort::Var`, and how a scheme like
   `in: S # List(S) -> Bool` is resolved once and instantiated fresh at
   every use site.
 - **[Sort Inference](sort-inference.md)** — Phase 3: the sort lattice,
   constraint generation, unification with subtyping, and the ranked
   backtracking search — the heart of the crate.
 - **[Lowering](lowering.md)** — Phase 4: emitting aterms, binary-aterm
   compatibility, and the known divergences from the mCRL2 toolset.

**Specification kinds built on the pipeline above:**

 - **[Specification Type Checking](../specification/index.md)** — how
   `ProcessSpecification`, `PbesSpecification`, and `PresSpecification` each
   build on the data checker, collecting their own declarations and then
   type checking every expression.
 - **[Span-Keyed Typing Info (LSP Support)](typing-info.md)** — the `TypingInfo` API
   that exposes typing facts by source `Span` for editor tooling.
