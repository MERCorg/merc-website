# Desugaring

This page defines the transformations of [type checking](index.md) that replace
surface syntax with special structure by plain declarations and applications:
structured sorts, anonymous structured sorts and built-in operator syntax. After
them, later passes have one code path for declarations and one for applications,
instead of one special case per surface construct. It assumes [Sort and name resolution, Definitions 1 to 4](name-resolution.md#def-variable-resolution).

## Structured sorts

<a id="def-structured-sort"></a>**Definition 1 (structured sort).** A structured sort declaration

```math
\[
\mathtt{sort}\ S = \mathtt{struct}\ c_1(\mathit{pr}_{1,1}{:}\,S_{1,1}, \ldots, \mathit{pr}_{1,k_1}{:}\,S_{1,k_1})?\mathit{is\_c}_1 \mid \cdots \mid c_n(\ldots)?\mathit{is\_c}_n
\]
```

is desugared, following Appendix B.10 of the book, into

- the sort `S` without a right-hand side;
- a constructor $c_i : S_{i,1} \# \dots \# S_{i,k_i} \to S$ for every
  alternative;
- a recogniser $\mathit{is\_c}_i : S \to \mathit{Bool}$ for every alternative
  that names one;
- a projection $\mathit{pr}_{i,j} : S \to S_{i,j}$ for every argument that names
  one;
- the defining equations of the recognisers and projections, and of `==`, `<`,
  `<=` and `less_total` on `S`.

The defining equations are not added to the user's specification but to the
[system-defined specification](system-specification.md) that accompanies it
([The system-defined specification, Definition 1](system-specification.md#def-system-defined-specification)).

## Anonymous structured sorts

An *anonymous* structured sort is a `struct` that occurs inside another sort
expression instead of as the right-hand side of a sort declaration, for example
in the sort of a mapping. Structurally identical structured sorts denote the same
sort in mCRL2. Anonymous structured sorts are replaced by references to named
declarations, before sort names are resolved, so that the desugaring of
Definition 1 only has to handle named structured sorts.

<a id="def-hoisting"></a>**Definition 2 (hoisting).** Every anonymous structured sort is replaced by a
reference to a named declaration with the same body, as follows. Identical bodies
are hoisted to the same declaration.

1. If it occurs inside a sort declaration, in a constructor argument or in the
   right-hand side of a non-structured alias, it is hoisted to a fresh
   declaration `@struct<n>` with that body, whose constructors, recognisers and
   projections are generated as in Definition 1.
2. Otherwise, in the sort of a constructor, mapping, equation variable or binder,
   it is hoisted to the declaration-position structured sort with the same body,
   if there is one, so that it shares that sort's constructors.
3. Otherwise, it is hoisted to a fresh declaration `@struct<n>` *without* a body,
   so that no constructors, recognisers or projections are generated for it.

For example, in

```mcrl2
sort D = struct c | d;
map f: struct c | d -> Bool;
```

the domain of `f` is hoisted to `D` by the second rule, so `f` can be applied to
the constructors `c` and `d` of `D`. Without the declaration of `D`, the third
rule applies: `c` and `d` are never declared, so `f` has no argument it can be
applied to. This is also what the mCRL2 toolset does with such a sort.

## Operator syntax {#operator-syntax}

<a id="def-operator-lowering"></a>**Definition 3 (operator lowering).** Built-in operator syntax is replaced by an
application of the operator's name: `x == y` becomes `==(x, y)`, the list
cons `[x]` becomes an application of the cons operator, and so on. Number
literals and container literals such as `0`, `[]` and `{}` are kept as their own
expression nodes, because their sort is chosen by [inference](sort-inference.md) rather
than declared.

After operator lowering, an operator is an ordinary, possibly overloaded or
polymorphic, name in the [signature](signature.md), and inference treats it the
same way as a user-declared mapping.
