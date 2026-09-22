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
numbered from zero per specification, like [`VarId`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/type.VarId.html) and `DefId`), and it
rewrites every [`SortExpressionKind::TypeVar(name)`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/enum.SortExpressionKind.html#variant.TypeVar) reference
in the specification to [`ResolvedTypeVar(TypeVarId)`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/enum.SortExpressionKind.html#variant.ResolvedTypeVar), the same
[`Reference`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/enum.SortExpressionKind.html#variant.Reference)-to-[`Resolved`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/enum.SortExpressionKind.html#variant.Resolved) shape ordinary sort resolution uses. A name that
matches no `type_var` declaration is a [`WellTypedError::UndefinedTypeVar`](https://mercorg.github.io/merc/merc_typecheck/signature/is_well_typed/enum.WellTypedError.html#variant.UndefinedTypeVar); a
`type_var` block declaring the same name twice is a
[`WellTypedError::DuplicateTypeVarDeclaration`](https://mercorg.github.io/merc/merc_typecheck/signature/is_well_typed/enum.WellTypedError.html#variant.DuplicateTypeVarDeclaration).

The built-in templates all declare their own `type_var` block now:
[`BUILTIN_SCHEME_TEMPLATE`](https://mercorg.github.io/merc/merc_typecheck/signature/standard_sorts/static.BUILTIN_SCHEME_TEMPLATE.html) (the `==`, `!=`, `<`, `<=`, `>`, `>=`, `less_total`,
`if` scheme, bundled from `comparison.mcrl2` and loaded in
`standard_sorts.rs`) opens with `type_var S;`, and each bundled
container template (`list.mcrl2`, `set.mcrl2`, `fset.mcrl2`, `bag.mcrl2`,
`fbag.mcrl2`, `function_update.mcrl2`) declares its own `S`/`T` the same way,
rather than leaving them as bare, unresolved sort references for later code
to match by name. Both go through one shared entry point, which parses the
template text and immediately resolves its type variables, so a template is
never seen with a dangling [`TypeVar`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/enum.SortExpressionKind.html#variant.TypeVar) node.

## `ResolvedSort::Var` and `PolySortScheme`

A [`ResolvedTypeVar(id)`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/enum.SortExpressionKind.html#variant.ResolvedTypeVar) sort expression resolves through the ordinary
sort-resolution path — the same one every other sort expression takes — onto a
dedicated lattice member, `ResolvedSort::Var(TypeVarId)`. This is what lets a
template's declaration be resolved and interned exactly like a concrete
declaration: `map in: S # List(S) -> Bool;` resolves to one [`ResolvedSortId`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/type.ResolvedSortId.html)
whose structure is `Var(s) # List(Var(s)) -> Bool` for a single [`TypeVarId`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/type.TypeVarId.html)
`s`, shared between both occurrences of `S`.

Every constructor and mapping declaration in a set of templates is collected
into one [`PolySortScheme`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.PolySortScheme.html) per declaration — `{ vars: Vec<TypeVarId>, sort:
ResolvedSortId }` — keyed by name into a `HashMap<String,
Vec<PolySortScheme>>`. [`Signature`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html) carries this table as a [`schemes`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.schemes) field
alongside [`constructors`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.constructors)/[`mappings`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.mappings), so a name lookup against a signature has
exactly one place to look, not a separate polymorphic table on the side:

- **The user-facing signature** (`ctx.signature`) gets [`schemes`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.schemes) from *all
  six* container/function-update templates plus [`BUILTIN_SCHEME_TEMPLATE`](https://mercorg.github.io/merc/merc_typecheck/signature/standard_sorts/static.BUILTIN_SCHEME_TEMPLATE.html). A
  user specification's own declarations never carry a `type_var` block in
  current usage, so this only ever *adds* names to the signature rather than
  colliding with anything the user wrote.
- **A `system` equation's `builtin_schemes`** ([`EquationRole::System`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.EquationRole.html#variant.System), see
  [the name-resolution table](system-specification.md#name-resolution-inside-a-system-equation))
  gets a narrower table, built from [`BUILTIN_SCHEME_TEMPLATE`](https://mercorg.github.io/merc/merc_typecheck/signature/standard_sorts/static.BUILTIN_SCHEME_TEMPLATE.html) alone — no
  container templates. `system` (basics and the desugared structs' own
  equations) never itself calls a container
  operation, so admitting the container schemes here would only risk a
  spurious tie against a struct override's own real symbols for no benefit;
  a container/function-update instantiation's own equations never reach this
  role at all, specialized from their template's already-proven typing by
  substitution instead — see [Materializing ground content at lowering
  time](system-specification.md#materializing-ground-content-at-lowering-time).
  That narrow table is memoized on the checking context, since the template it
  reads is process-wide, not per-equation.

## Checking a template's equations once, rigidly

A template's own defining equations (`bag.mcrl2`'s `@zero_ == @one_`, and the
rest) are checked exactly once per template, not once per instantiation:
Phase-3 inference runs over them with the template's `type_var`-declared
sort(s) held **rigid** — a skolem constant rather than a unification variable
— and the result, a [`TemplateCheck { type_vars, typings }`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.TemplateCheck.html), is memoized on the
checking context. `type_vars` here is collected directly from the template's
own `type_var` declarations, a separate list from `PolySortScheme.vars` above
(which stays unread — nothing yet needs a scheme's bound variables as data,
since instantiation discovers them structurally by walking `sort`).
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

Instantiation turns a [`PolySortScheme`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.PolySortScheme.html)'s already-interned `sort` into a fresh
sort node for one occurrence: it walks the [`ResolvedSort`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html) structurally, and
every `Var(id)` it reaches becomes one fresh
unification variable, memoized in a local `HashMap<TypeVarId, InferSortId>`
so two occurrences of the same `id` within *this one instantiation* share the
same variable — the mechanism that makes `S` mean "the same `S`" on both
sides of `in: S # List(S) -> Bool`. Every occurrence gets a fresh `HashMap`,
so two occurrences of `in` in the same equation never share a variable with
each other.

This replaces an older design where a template's sort variables were bare,
unresolved `Reference` nodes matched by name during instantiation — a
syntax-tree walk with no counterpart in the interned lattice. Because
[`ResolvedTypeVar`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/enum.SortExpressionKind.html#variant.ResolvedTypeVar)/`ResolvedSort::Var` are resolved once, up front, alongside
every other sort, instantiation has no name-keyed path left to fall back to: a
scheme's `sort` can only ever contain `Var`, never a bare name.

## Real declaration spans for system-defined symbols

The bundled template files are registered into the shared [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html) as
virtual documents (e.g. `<builtin>/list.mcrl2`), the same offsetting technique
[`%import` resolution](name-resolution.md) uses. This is what lets the checking
context's table of system symbol spans — and so
[`ResolvedName::SystemDefined`'s `declaration`](typing-info.md) — carry a real,
renderable span for a system-defined constructor or mapping (`[]: List(S)`,
`in`, …) instead of an empty placeholder span: hovering or jumping to one of
these symbols lands in the actual bundled `.mcrl2` source, not nowhere.

## What's still open

Whether a user specification should ever be allowed to declare its own
`type_var` block — reaching user-facing generics, rather than staying an
internal representation used only for Appendix B — remains open. Nothing
described above requires it; every `type_var` block in the pipeline today
comes from a bundled template, never from user-written `mcrl2` text.
