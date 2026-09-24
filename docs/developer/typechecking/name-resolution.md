# Phase 0: Sort & Name Resolution

This page covers the first phases of the pipeline: the syntactic groundwork that
runs directly on the [`merc_syntax`](https://mercorg.github.io/merc/merc_syntax/index.html) AST, before any sort is computed. Nothing
here depends on the signature or on inference.

## Variable Name Resolution

Before any other phase runs, a variable-resolution pass rewrites every variable
occurrence. A `var`-block equation variable, but also a
`sum`/`dist`/quantifier/`lambda`/comprehension/`whr` binder introduced locally
*within* an equation body is rewritten from a plain reference to the
corresponding unique id, tying the occurrence to its declaration. The binder's
own declaration node is given that same
[`VarId`](https://mercorg.github.io/merc/merc_syntax/type.VarId.html)
([`IdDecl::var_id`](https://mercorg.github.io/merc/merc_syntax/struct.IdDecl.html#structfield.var_id),
or the equivalent field on a `whr`/fixpoint-variable assignment). Resolution
mutates the tree in place and returns nothing of its own.

**IDs are unique only within the resolution call that produced them.** Each
entry point allocates its own fresh
[`VarIdAllocator`](https://mercorg.github.io/merc/merc_syntax/type.VarIdAllocator.html)
starting back at zero. A whole data specification's equations share one
allocator across every `var`-block, so no two binders in that specification
collide. But a caller-supplied expression checked afterwards against that same,
already-resolved specification (via
[`DataSpecification::typecheck_expression`](https://mercorg.github.io/merc/merc_typecheck/struct.DataSpecification.html#method.typecheck_expression))
is resolved by its own later call to
[`resolve_data_expr_variables`](https://mercorg.github.io/merc/merc_typecheck/resolution/variable_resolution/fn.resolve_data_expr_variables.html),
with a *separate* allocator that starts over from the same numeric range — its
[`VarId`](https://mercorg.github.io/merc/merc_syntax/type.VarId.html)s may
coincide numerically with ones the specification's own equations already used. A
[`VariableSpans`](https://mercorg.github.io/merc/merc_typecheck/typing_info/struct.VariableSpans.html)
map (and the
[`TypingInfo`](https://mercorg.github.io/merc/merc_typecheck/struct.TypingInfo.html)
built from it) is therefore always built and consumed within the single
resolution call that produced its
[`VarId`](https://mercorg.github.io/merc/merc_syntax/type.VarId.html)s, never
merged across two independently resolved expressions.

A [`type_var`](polymorphism.md) block is resolved by a separate pass — it assigns
each `type_var` declaration its own [`TypeVarId`](https://mercorg.github.io/merc/merc_syntax/type.TypeVarId.html) and rewrites every
[`TypeVar(name)`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.TypeVar) sort reference to [`ResolvedTypeVar(TypeVarId)`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.ResolvedTypeVar).

## Sort Name Resolution

This phase establishes what sorts exist and rejects malformed sort declarations,
still operating directly on the AST rather than on any interned representation.

### Function-sort domain flattening

Before name resolution or any of the other sort-layer checks below run,
function sorts with product domains such as `(A # B) -> C` are flattened into
a single multi-argument form `A # B -> C`, so that every later phase sees one
uniform representation of a function sort rather than having to special-case a
[`Product`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.Product) domain spine.

### Name resolution

Sort-name resolution assigns a sort id ([`SortId`](https://mercorg.github.io/merc/merc_syntax/type.SortId.html)) to every `sort`
declaration, and then every sort *reference* in the specification — including a
binder sort buried inside an equation body, such as a quantifier variable, not
just a declaration-level sort — is rewritten from [`Reference(name)`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.Reference) to
[`Resolved(name, sort_id)`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.Resolved). Duplicate and undefined sort names are rejected, while
byte-identical duplicate declarations (`sort D; D;`) are (silently) accepted as
one.

### Alias

Circular sort aliases are rejected by two separate searches, run over the
*resolved* declarations:

- **Circularity.** An alias may not reach itself through basic sorts,
  containers, or function sorts. A structured (`struct`) sort terminates the
  search instead of rejecting it, because recursion through a constructor is
  inductively well-founded — a `struct` can always be built from a
  non-recursive alternative first:

  ```mcrl2
  sort Tree = struct leaf | node(Tree, Tree);
  ```

  This is accepted: `Tree` is a `struct`, so the search stops there rather
  than unfolding `Tree` again inside `node`'s arguments.

- **Function-sort loops.** A second search continues *through* structured
  sorts as well, and rejects a cycle that passes through a function sort or an
  unbounded `Set`/`Bag` container even when a `struct` sits along the way:

  ```mcrl2
  sort S = struct f(S -> Bool);
  ```

  is rejected — `S` reaches itself through a function-sort argument, and a
  function sort has no cardinality-consistent interpretation for such a
  recursion. A loop through a `List`, `FSet`, or `FBag` container is fine,
  since those are inductively founded on the empty case the same way a
  `struct` alternative is.

### Normalization

Normalization expands aliases to a canonical form, since they are not circular.
a non-structured alias (`sort D = Nat;`, `sort L = List(D);`) is replaced by its
recursively normalized definition, so the alias and the sort it stands for
become indistinguishable and sort equality is structural throughout the rest of
the pipeline. A structured-sort alias instead stays a named representative — it
keeps its own name rather than being inlined — both because structured sorts are
identified by name (two structurally identical `struct`s are still different
sorts unless declared as the same name) and because expanding a recursive
`struct` definition would not terminate.
