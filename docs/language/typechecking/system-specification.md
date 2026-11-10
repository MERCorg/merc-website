# The system-defined specification

The standard data types of Appendix B of the book (`Bool`, `Pos`, `Nat`, `Int`,
`Real`, the containers `List`, `Set`, `Bag`, `FSet` and `FBag`, and function
update) are not written by the user, but almost every specification needs them.
This page defines how [type checking](index.md) provides them, and why they are
kept apart from the user's own declarations. It assumes the definitions of
[Sort and name resolution](name-resolution.md), [Desugaring](desugaring.md) and
[Signature and well-typedness](signature.md).

## Definitions {#definitions}

The operations of Appendix B fall into two groups, by how many sorts they range
over.

- **Basic-sort operations**, such as `&&`, `+`, `*` and the orderings on numbers,
  range over the five basic sorts only. They are declared concretely: each is an
  ordinary finite set of overloads.
- **Polymorphic operations** exist for every sort: the comparison operators `==`,
  `!=`, `<`, `<=`, `>`, `>=`, `less_total` and `if`, the container operations
  (`in`, `#`, `|>`, `head`, …) and function update. They are declared once, as
  polymorphic schemes ([Type variables and polymorphic schemes, Definition 1](polymorphism.md#def-scheme)), such as `==` as
  $\forall S.\ S \# S \to \mathit{Bool}$ and `if` as
  $\forall S.\ \mathit{Bool} \# S \# S \to S$. This mirrors the polymorphic
  built-in symbol table of mCRL2.

`less_total` is not user-facing: it is a total order on `S` that the set and bag
sorts use to keep their elements sorted, also for a sort whose `<` is not total,
such as sets ordered by inclusion.

<a id="def-system-defined-specification"></a>**Definition 1 (system-defined specification).** The *system-defined
specification* of a data specification consists of

- the declarations and defining equations of the basic sorts;
- the defining equations of its structured sorts
  ([Desugaring, Definition 1](desugaring.md#def-structured-sort));
- system-internal sorts that these need, such as `@NatPair` of the number
  templates.

The ground instances of the polymorphic operations, such as
`in: Nat # List(Nat) -> Bool` and its defining equations, are not part of it.
They are generated, only for the sorts that actually occur, at
[lowering](../../rewriting/data/lowering.md#materializing-ground-content-at-lowering-time),
the point where a rewriter needs concrete symbols instead of schemes.

<a id="def-reserved-names"></a>**Definition 2 (reserved names).** A user constructor or mapping may not be
named

- like a constructor or mapping of the system-defined specification;
- like a polymorphic operation;
- with a name that starts with `@`.

The reserved names make the signature unambiguous: a user `map in: ...` is
rejected outright, so the question whether it is one more overload of the scheme
`in` or a conflict with it never arises.

## Why it is not checked as a user specification

The system-defined specification is checked by almost the same passes as the
user's own declarations, with two differences.

- It declares things that a user may not. The basic-sort templates give `Nat`,
  `Pos`, `Int` and `Real` their constructors (`@c0: Nat`, …), which
  condition 4 of [Signature and well-typedness, Definition 2](signature.md#def-well-typed-declarations) forbids, and they use
  reserved `@`-names throughout. Its declarations are therefore checked as
  *trusted*, which skips exactly the rule against constructors of a basic sort.
  Every other condition of that definition still applies, so that a mistake in a
  bundled template is reported rather than accepted as generated content.
- A user declaration may not shadow it, which is Definition 2.

Its sort names are resolved by the same pass and against the same table as the
user's ([Sort and name resolution, Definition 2](name-resolution.md#def-sort-name-resolution)): system-internal sorts are added to the user's sort
declarations before sort names are resolved, so `@NatPair` has an ordinary sort
identifier, and there is no second namespace. Its equations are checked by the
same well-formedness rules and the same [sort inference](sort-inference.md) as
user equations.

## Name resolution in system equations

User equations, system equations and the equations of
[templates](polymorphism.md#checking-a-template-once) all resolve names in the
same order against the same signature, which contains every user declaration,
every basic-sort operation and every scheme, and they share constraint
generation, unification and the ranked search. They differ only in where the
sort of a variable comes from, in where their typing is stored, and in that only
user equations contribute [typing information](typing-info.md): system and
template equations have no source position in the user's document.

The equations of a ground instance of a template are not inferred at all. They
were checked once for the template ([Type variables and polymorphic schemes, Theorem 1](polymorphism.md#thm-checking-a-template-once)), and their typing is obtained by
substituting the instance's sorts into that typing.

## Why polymorphism is needed

A first approach would instantiate every polymorphic operation for every element
sort that occurs, turning `in: S # List(S) -> Bool` into the overloads
`in: Nat # List(Nat) -> Bool`, `in: Pos # List(Pos) -> Bool`, …, and resolve them
into the signature like user overloads. This does not work: two instances of the
same template declare symbols with the same name (`[]: List(D)` and
`[]: List(E)`, `@zero_: Bag(Nat)` and `@zero_: Bag(D)`), so checking the
equations of one instance can pick up a declaration of another instance as an
extra overload, and report a well-typed equation as ambiguous. With schemes,
there is only ever one declaration per template during checking, and every
ground instance is produced afterwards by substitution.

## Source locations {#source-locations}

The system-defined declarations are registered in the same
[source map](../parsing/source_map.md) as the user's files, as virtual documents
such as `<builtin>/nat.mcrl2`. This is why
[`DataSpecification::from_untyped_with`](https://mercorg.github.io/merc/merc_typecheck/)
takes the source map that the specification was parsed with: a diagnostic or a
go-to-definition query can then point into system-defined content just as into a
user file. A use of a basic-sort operation is reported as
`ResolvedName::SystemDefined`,
with its location in the virtual document. A use of a polymorphic operation is
reported as
`ResolvedName::Builtin`,
without a location, since its meaning follows from the inferred argument sorts
rather than from one declaration.
