# Sort and name resolution

This page defines the syntactic groundwork of [type checking](index.md): how
variable occurrences and sort names are tied to their declarations, when a set of
sort aliases is well-founded, and the normal form of sorts that the rest of the
pipeline works with. These passes run directly on the
[`merc_syntax`](https://mercorg.github.io/merc/merc_syntax/index.html) syntax
tree, before any sort is inferred, and depend on neither the signature nor
inference.

## Variables

<a id="def-variable-resolution"></a>**Definition 1 (variable resolution).** A *binder* is a declaration of a data
variable: a variable of a `var` block, a parameter of a process, PBES or PRES
equation, or a variable bound by `sum`, `dist`, a quantifier, `lambda`, a set or
bag comprehension, a `whr` clause, or `inf`/`sup`/`sum` in a PRES. Variable
resolution assigns every binder a *variable identifier*, and replaces every
variable occurrence by the identifier of the innermost binder of that name whose
scope contains it. An occurrence with no such binder is left unresolved; it is a
constructor or mapping name, or else an undeclared name that inference reports.

Variable identifiers are unique within one resolution call only: every call
numbers its binders from zero. A whole data specification is resolved in one
call, so its binders never collide. An expression that is checked later against
an already resolved specification, by
[`DataSpecification::typecheck_expression`](https://mercorg.github.io/merc/merc_typecheck/),
is resolved by a call of its own, starting from an empty scope, and its
identifiers may coincide numerically with those of the specification. The
identifiers, and the table from identifiers to declaration spans built in the
same call, are therefore only meaningful together.

Resolving variables before inference is possible because a variable occurrence is
*context-free*: which binder it refers to follows from the syntax alone, without
knowing any sort. Constructor and mapping names, by contrast, can be overloaded,
and are only resolved by [sort inference](sort-inference.md#resolving-names).
Because every binder, also one nested inside a single expression, is resolved by
this pass, inference looks up the sort of a variable by its identifier only and
needs no scopes of its own.

The type variables of a `type_var` block are resolved by a similar, separate pass
([Type variables and polymorphic schemes, Definition 1](polymorphism.md#def-scheme)).

## Sort names

<a id="def-sort-name-resolution"></a>**Definition 2 (sort-name resolution).** Sort-name resolution assigns a *sort
identifier* to every `sort` declaration and replaces every sort reference, also
the sort of a binder inside an equation, by the identifier of the declaration of
that name. A reference to an undeclared sort is rejected, as is a sort name
declared twice with different right-hand sides; a declaration repeated verbatim
(`sort D; D;`) counts as one.

Before this pass, a function sort with a product domain, `(A # B) -> C`, is
flattened to the multi-argument function sort `A # B -> C`, so that every later
pass sees one representation of a function sort.

## Aliases {#aliases}

An *alias* is a sort declaration `sort A = s;` with a right-hand side $s$. A
*structured alias* is one whose right-hand side is a `struct`.

<a id="def-well-founded-aliases"></a>**Definition 3 (well-founded aliases).** The aliases of a specification are
*well-founded* if both of the following hold.

1. **No circularity.** No alias reaches itself through the sorts its right-hand
   side refers to, following references through aliases, container sorts and
   function sorts, but not into the arguments of a structured sort.
2. **No recursion through a function sort.** No alias reaches itself through any
   path, now also into the arguments of a structured sort, that passes through a
   function sort or a `Set` or `Bag` container.

The first condition stops at a structured sort because recursion through a
constructor is well-founded: a structured sort can always be built from a
non-recursive alternative first. So

```mcrl2
sort Tree = struct leaf | node(Tree, Tree);
```

is accepted. The second condition rejects

```mcrl2
sort S = struct f(S -> Bool);
```

because a function sort has no interpretation for such a recursion. A recursion
through a `List`, `FSet` or `FBag` container is allowed, since those are
founded on their empty value just as a structured sort is founded on its
non-recursive alternatives.

These conditions are checked on the resolved declarations, before structured
sorts are [desugared](desugaring.md), because the checks have to tell structured
sorts apart from other sorts.

<a id="def-sort-normal-form"></a>**Definition 4 (sort normal form).** The *normal form* of a sort replaces every
reference to a non-structured alias by the normal form of its right-hand side,
and leaves every other sort reference, including a reference to a structured
alias, unchanged.

For well-founded aliases the normal form exists: by the first condition of
Definition 3, expanding non-structured aliases terminates. A structured alias is
not expanded, because structured sorts are identified by name (two structurally
identical structured sorts are different sorts unless they are the same
declaration) and because expanding a recursive structured sort would not
terminate. After normalisation, `sort D = Nat;` makes `D` and `Nat` the same
sort, and sort equality is structural for the rest of the pipeline.
