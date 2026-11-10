# Overview

The [`merc_typecheck`](https://mercorg.github.io/merc/merc_typecheck/index.html)
crate type checks mCRL2 data specifications, following the definitions of
*Modeling and Analysis of Communicating Systems* (Groote and Mousavi, MIT Press
2014), cited below as "the book". Type checking turns the untyped syntax tree of
[`merc_syntax`](https://mercorg.github.io/merc/merc_syntax/index.html) into a
well-typed specification: it resolves every name, decides the sort of every
expression, chooses between overloaded operators, and inserts the implicit
coercions that the surface language leaves out, such as reading a natural number
where a real number is expected.

The pages of this section cover, in order:

- [Sort and name resolution](name-resolution.md): variables, sort names, alias
  well-foundedness and normalisation ([Sort and name resolution, Definitions 1 to 4](name-resolution.md#def-variable-resolution)).
- [Desugaring](desugaring.md): structured sorts and built-in operator syntax
  ([Desugaring, Definitions 1 to 3](desugaring.md#def-structured-sort)).
- [Signature and well-typedness](signature.md): the signature $(S, C, M)$, the
  well-typedness conditions and non-empty sorts ([Signature and well-typedness, Definitions 1 to 3](signature.md#def-signature), [Signature and well-typedness, Theorem 1](signature.md#thm-computing-non-empty-sorts)).
- [The system-defined specification](system-specification.md): the standard data
  types of Appendix B and how they are checked ([The system-defined specification, Definitions 1 and 2](system-specification.md#def-system-defined-specification)).
- [Type variables and polymorphic schemes](polymorphism.md): schemes, their
  instances, and checking a template once ([Type variables and polymorphic schemes, Definitions 1 and 2](polymorphism.md#def-scheme), [Type variables and polymorphic schemes, Theorem 1](polymorphism.md#thm-checking-a-template-once)).
- [Sort inference](sort-inference.md): the subsort order, coercions, constraints
  and their ranking ([Sort inference, Definitions 1 to 4](sort-inference.md#def-sorts-and-subsorts)). It builds on two general components:
  ranked backtracking ([Ranked Backtracking, Theorems 1 to 3](inference/ranked-backtracking.md#thm-first-success-is-exact)), the
  search for the best typing, and the unifier
  ([The Unifier, Definition 1](inference/unification.md#def-sorts-with-holes), [The Unifier, Theorem 1](inference/unification.md#thm-unification)), which decides sort equality.
- [Typing information](typing-info.md): the span-keyed typing facts exposed to
  editor tooling ([Typing information, Definitions 1 and 2](typing-info.md#def-typing-information)).

## Architecture {#architecture}

Type checking a data specification is a pipeline of passes, each with a
well-defined input and output, run by
`DataSpecification::from_untyped`.
The passes, in the order the code runs them, are:

1. **Variable resolution.** Every variable occurrence is tied to its binder
   ([Sort and name resolution, Definition 1](name-resolution.md#def-variable-resolution)).
2. **Hoisting anonymous structured sorts** into named declarations
   ([Desugaring, Definition 2](desugaring.md#def-hoisting)), and flattening product domains of function sorts.
3. **Type-variable resolution** for `type_var` blocks ([Type variables and polymorphic schemes, Definition 1](polymorphism.md#def-scheme)).
4. **Sort-name resolution** ([Sort and name resolution, Definition 2](name-resolution.md#def-sort-name-resolution)), including the sorts of the
   system-defined specification ([The system-defined specification, Definition 1](system-specification.md#def-system-defined-specification)).
5. **Alias checks** ([Sort and name resolution, Definition 3](name-resolution.md#def-well-founded-aliases)), before desugaring, because they need to see
   the structured sorts.
6. **Desugaring structured sorts** into constructors, recognisers and
   projections ([Desugaring, Definition 1](desugaring.md#def-structured-sort)).
7. **The signature** and its well-typedness conditions ([Signature and well-typedness, Definitions 1 and 2](signature.md#def-signature)),
   before alias expansion, so that errors refer to sorts as the user wrote them.
8. **Alias normalisation** ([Sort and name resolution, Definition 4](name-resolution.md#def-sort-normal-form)), followed by the remaining
   well-typedness conditions and the non-emptiness check ([Signature and well-typedness, Definition 3](signature.md#def-non-empty-sorts)), which
   need the normalised view.
9. **Operator lowering** ([Desugaring, Definition 3](desugaring.md#def-operator-lowering)), and the check that no user declaration
   redeclares a system-defined symbol ([The system-defined specification, Definition 2](system-specification.md#def-reserved-names)).
10. **The system-defined specification**: the defining equations of the
    structured sorts are added, and its signature is resolved.
11. **Template checking**: the equations of every container and function-update
    template are checked once, with their type variables rigid ([Type variables and polymorphic schemes, Theorem 1](polymorphism.md#thm-checking-a-template-once)).
12. **Sort inference** over every user equation ([Sort inference, Definitions 1 to 4](sort-inference.md#def-sorts-and-subsorts)), and then
    over every system-defined equation.

During type checking, sorts are interned indices into one table, so sort
equality is a single integer comparison, and typings are kept in side tables
keyed by expression. Only the final [lowering](../../rewriting/data/lowering.md) phase
produces the maximally shared term representation that the rest of merc, such as
[`merc_sabre`](https://mercorg.github.io/merc/merc_sabre/index.html) and
[`merc_explore`](https://mercorg.github.io/merc/merc_explore/index.html),
consumes.

Specifications built on a data specification reuse this pipeline:
`ProcessSpecification`
and
`ModalSpecification`
in `merc_typecheck` itself, and the PBES and PRES specifications in
[`merc_pbes`](https://mercorg.github.io/merc/merc_pbes/index.html) and
[`merc_pres`](https://mercorg.github.io/merc/merc_pres/index.html), which use
the building blocks that `merc_typecheck` exposes behind its `internal` feature.
See [Specification type checking](../specification/index.md).
