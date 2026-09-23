# Type Variables & Polymorphic Schemes

[The System-Defined Specification](system-specification.md#the-polymorphic-signature)
explains *why* the container/function-update operations and the comparison
operators/`if` are typed as schemes rather than instantiated concretely for
every sort. This page covers the mechanics: how a scheme's own bound
variables are declared and resolved, how they end up in the
[sort lattice](sort-inference.md#the-sort-lattice), and how a scheme is
instantiated fresh at each use site.

## The `type_var` block

A scheme's bound sort variables are declared the same way an equation's
variables are declared in a `var` block, just for sorts: a `type_var S;`
block, parsed by the same grammar as any other specification section
([`TypeVarSpec`](https://mercorg.github.io/merc/merc_syntax/parse/enum.Rule.html#variant.TypeVarSpec)). Type-variable resolution runs early in the construction of a
[`DataSpecification`](https://mercorg.github.io/merc/merc_typecheck/data_specification/struct.DataSpecification.html) — right after equation-variable resolution and struct
hoisting, before ordinary sort-name resolution — and does two things: it
assigns each `type_var` declaration a [`TypeVarId`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/type.TypeVarId.html) (a [`TagIndex`](https://mercorg.github.io/merc/merc_utilities/tagged_index/struct.TagIndex.html)-based id,
numbered from zero per specification, like [`VarId`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/type.VarId.html) and [`SortId`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/type.SortId.html)), and it
rewrites every [`SortExpressionKind::TypeVar(name)`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.TypeVar) reference
in the specification to [`ResolvedTypeVar(TypeVarId)`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.ResolvedTypeVar), the same
[`Reference`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.Reference)-to-[`Resolved`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.Resolved) shape ordinary sort resolution uses. A name that
matches no `type_var` declaration is a [`WellTypedError::UndefinedTypeVar`](https://mercorg.github.io/merc/merc_typecheck/signature/is_well_typed/enum.WellTypedError.html#variant.UndefinedTypeVar); a
`type_var` block declaring the same name twice is a
[`WellTypedError::DuplicateTypeVarDeclaration`](https://mercorg.github.io/merc/merc_typecheck/signature/is_well_typed/enum.WellTypedError.html#variant.DuplicateTypeVarDeclaration).

The built-in templates all declare their own `type_var` block now:
[`BUILTIN_SCHEME_TEMPLATE`](https://mercorg.github.io/merc/merc_typecheck/signature/standard_sorts/static.BUILTIN_SCHEME_TEMPLATE.html) (the `==`, `!=`, `<`, `<=`, `>`, `>=`, `less_total`,
`if` scheme, bundled from `comparison.mcrl2` and loaded in
`standard_sorts.rs`) opens with `type_var S;`, and each bundled
container template (`list.mcrl2`, `set.mcrl2`, `fset.mcrl2`, `bag.mcrl2`,
`fbag.mcrl2`) declares its own `S`/`T` the same way,
rather than leaving them as bare, unresolved sort references for later code
to match by name. Both go through one shared entry point, which parses the
template text and immediately resolves its type variables, so a template is
never seen with a dangling [`TypeVar`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.TypeVar) node.
Function-update has no bundled template file of its own: its scheme is
generated programmatically, per arity, the first time that arity is
encountered at a call site — see below.

## `ResolvedSort::TypeVar` and `PolySortScheme`

A [`ResolvedTypeVar(id)`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.ResolvedTypeVar) sort expression resolves through the ordinary
sort-resolution path — the same one every other sort expression takes — onto a
dedicated lattice member, [`ResolvedSort::TypeVar`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.TypeVar)([`TypeVarId`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/type.TypeVarId.html)). This is what lets a
template's declaration be resolved and interned exactly like a concrete
declaration: `map in: S # List(S) -> Bool;` resolves to one [`ResolvedSortId`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/type.ResolvedSortId.html)
whose structure is `TypeVar(s) # List(TypeVar(s)) -> Bool` (each [`TypeVar`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.TypeVar) node
the same lattice member) for a single [`TypeVarId`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/type.TypeVarId.html)
`s`, shared between both occurrences of `S`.

Every constructor and mapping declaration in a set of templates is collected
into one [`PolySortScheme`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.PolySortScheme.html) per declaration — `{ sort: ResolvedSortId }`, a single
field holding the already-interned, already-resolved sort — keyed by name into
a [`HashMap`](https://doc.rust-lang.org/std/collections/struct.HashMap.html) from name to a [`Vec`](https://doc.rust-lang.org/std/vec/struct.Vec.html) of [`PolySortScheme`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.PolySortScheme.html)s. There is no separate field listing a
scheme's bound variables: a scheme's `sort` is walked structurally at
instantiation time (see below), and every [`TypeVar(id)`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.TypeVar) node it contains
*is* the set of variables that need a fresh unification variable, discovered
on the fly rather than precomputed and stored. [`Signature`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html) carries the
scheme table as a [`schemes`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.schemes) field
alongside [`constructors`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.constructors)/[`mappings`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.mappings), so a name lookup against a signature has
exactly one place to look, not a separate polymorphic table on the side:

- **The user-facing signature** ([`ctx.signature`](https://mercorg.github.io/merc/merc_typecheck/inference/context/struct.TypeCheckContext.html#structfield.signature)) gets [`schemes`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.schemes) from the
  five container templates (`list`, `set`, `fset`, `bag`, `fbag`) chained with
  [`BUILTIN_SCHEME_TEMPLATE`](https://mercorg.github.io/merc/merc_typecheck/signature/standard_sorts/static.BUILTIN_SCHEME_TEMPLATE.html) — six *sources* in total. A
  user specification's own declarations never carry a `type_var` block in
  current usage, so this only ever *adds* names to the signature rather than
  colliding with anything the user wrote.
- **Function-update is not part of this initial build at all.** It has no
  bundled template file, and no fixed arity to declare a scheme for ahead of
  time. Instead, the first time a given arity is encountered at a call site,
  [`typecheck_function_update_template`](https://mercorg.github.io/merc/merc_typecheck/signature/standard_sorts/fn.typecheck_function_update_template.html) generates that arity's template text
  programmatically, type-checks it once (rigidly, the same as the bundled
  templates below), and merges its one new scheme permanently into
  [`ctx.signature`](https://mercorg.github.io/merc/merc_typecheck/inference/context/struct.TypeCheckContext.html#structfield.signature) so later call sites of the same arity reuse it.
- Every role — checking the user's own equations, `system`'s basics and
  desugared-struct equations, and a template's own equations — shares the
  same one pooled [`ctx.signature`](https://mercorg.github.io/merc/merc_typecheck/inference/context/struct.TypeCheckContext.html#structfield.signature) and the same unfiltered candidate set; see
  [`EquationRole`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.EquationRole.html)'s own doc comment and [the name-resolution
  table](system-specification.md#name-resolution-inside-a-system-equation).
  What differs between roles is only where a binder/equation-variable's sort
  is resolved from, and which spec an [`EqnSpecId`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/type.EqnSpecId.html) indexes into — there is no
  separate, narrower scheme table for any one role.

## Checking a template's equations once, rigidly

A template's own defining equations (`bag.mcrl2`'s `@zero_ == @one_`, and the
rest) are checked exactly once per template, not once per instantiation:
Phase-3 inference runs over them with the template's `type_var`-declared
sort(s) held **rigid** — a skolem constant rather than a unification variable
— and the result, a [`TemplateCheck { type_vars, typings }`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.TemplateCheck.html), is memoized on the
checking context. [`type_vars`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.TemplateCheck.html#structfield.type_vars) here is collected directly from the template's
own `type_var` declarations. [`PolySortScheme`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.PolySortScheme.html) itself carries no equivalent
list — it stores only the scheme's interned [`sort`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.PolySortScheme.html#structfield.sort) — since instantiation
never needs a scheme's bound variables as precomputed data; it discovers them
structurally by walking [`sort`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.PolySortScheme.html#structfield.sort) and collecting every [`TypeVar`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.TypeVar) node it finds.
Specialization uses [`TemplateCheck.type_vars`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.TemplateCheck.html#structfield.type_vars), together with the concrete sorts
each
[`TemplateInstantiation`](system-specification.md#materializing-ground-content-at-lowering-time)
records, to turn that one proven typing into the typing of a concrete
instantiation by substitution instead of re-inference. See [Checking the
container templates: once,
rigidly](system-specification.md#checking-the-container-templates-once-rigidly)
and [Materializing ground content at lowering
time](system-specification.md#materializing-ground-content-at-lowering-time)
for where each half of this runs.

## Instantiating a scheme

Instantiation turns a [`PolySortScheme`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.PolySortScheme.html)'s already-interned [`sort`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.PolySortScheme.html#structfield.sort) into a fresh
sort node for one occurrence: it walks the [`ResolvedSort`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html) structurally, and
every [`TypeVar(id)`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.TypeVar) it reaches becomes one fresh
unification variable, memoized in a local [`HashMap`](https://doc.rust-lang.org/std/collections/struct.HashMap.html) from [`TypeVarId`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/type.TypeVarId.html) to [`InferSortId`](https://mercorg.github.io/merc/merc_typecheck/inference/unification/type.InferSortId.html)
so two occurrences of the same `id` within *this one instantiation* share the
same variable — the mechanism that makes `S` mean "the same `S`" on both
sides of `in: S # List(S) -> Bool`. Every occurrence gets a fresh [`HashMap`](https://doc.rust-lang.org/std/collections/struct.HashMap.html),
so two occurrences of `in` in the same equation never share a variable with
each other.

This replaces an older design where a template's sort variables were bare,
unresolved [`Reference`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.Reference) nodes matched by name during instantiation — a
syntax-tree walk with no counterpart in the interned lattice. Because
[`ResolvedTypeVar`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.ResolvedTypeVar)/[`ResolvedSort::TypeVar`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.TypeVar) are resolved once, up front, alongside
every other sort, instantiation has no name-keyed path left to fall back to: a
scheme's [`sort`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.PolySortScheme.html#structfield.sort) can only ever contain [`TypeVar`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.TypeVar), never a bare name.

## Real declaration spans for system-defined symbols

The bundled template files are registered into the shared [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html) as
virtual documents (e.g. `<builtin>/list.mcrl2`), the same offsetting technique
[`%import` resolution](name-resolution.md) uses. This is what lets the checking
context's table of system symbol spans ([`system_symbol_spans`](https://mercorg.github.io/merc/merc_typecheck/inference/context/struct.TypeCheckContext.html#structfield.system_symbol_spans)) — and so
[`ResolvedName::SystemDefined`](https://mercorg.github.io/merc/merc_typecheck/typing_info/enum.ResolvedName.html#variant.SystemDefined)'s [`declaration`](https://mercorg.github.io/merc/merc_typecheck/typing_info/enum.ResolvedName.html#variant.SystemDefined.field.declaration) (see [typing info](typing-info.md)) — carry a real,
renderable span for a system-defined constructor or mapping (`[]: List(S)`,
`in`, …) instead of an empty placeholder span: hovering or jumping to one of
these symbols lands in the actual bundled `.mcrl2` source, not nowhere.

## What's still open

Whether a user specification should ever be allowed to declare its own
`type_var` block — reaching user-facing generics, rather than staying an
internal representation used only for Appendix B — remains open. Nothing
described above requires it; every `type_var` block in the pipeline today
comes from a bundled template, never from user-written `mcrl2` text.
