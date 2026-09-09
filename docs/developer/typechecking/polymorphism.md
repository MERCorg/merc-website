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
(`TypeVarSpec`). `resolve_type_var_ids` runs early in
`DataSpecification::from_untyped_with` — right after equation-variable
resolution and struct hoisting, before ordinary sort-name resolution — and
does two things: it assigns each `type_var` declaration a `TypeVarId` (a
`TagIndex`-based id, numbered from zero per specification, like `VarId` and
`DefId`), and it rewrites every `SortExpressionKind::TypeVar(name)` reference
in the specification to `ResolvedTypeVar(TypeVarId)`, the same
`Reference`-to-`Resolved` shape ordinary sort resolution uses. A name that
matches no `type_var` declaration is a `WellTypedError::UndefinedTypeVar`; a
`type_var` block declaring the same name twice is a
`WellTypedError::DuplicateTypeVarDeclaration`.

The built-in templates all declare their own `type_var` block now:
`BUILTIN_SCHEME_TEMPLATE` (the inline `==`, `!=`, `<`, `<=`, `>`, `>=`, `if`
scheme, in `builtins.rs`) opens with `type_var S;`, and each bundled
container template (`list.mcrl2`, `set.mcrl2`, `fset.mcrl2`, `bag.mcrl2`,
`fbag.mcrl2`, `function_update.mcrl2`) declares its own `S`/`T` the same way,
rather than leaving them as bare, unresolved sort references for later code
to match by name. `parse_template_bare` — the shared entry point both use —
parses the template text and immediately runs `resolve_type_var_ids` over it,
so a template is never seen with a dangling `TypeVar` node.

## `ResolvedSort::Var` and `PolySortScheme`

A `ResolvedTypeVar(id)` sort expression resolves through the ordinary
`resolve_sort` path — the same function used for every other sort
expression — onto a dedicated lattice member, `ResolvedSort::Var(TypeVarId)`.
This is what lets a template's declaration be resolved and interned exactly
like a concrete declaration: `map in: S # List(S) -> Bool;` resolves to one
`ResolvedSortId` whose structure is `Var(s) # List(Var(s)) -> Bool` for a
single `TypeVarId` `s`, shared between both occurrences of `S`.

`build_polymorphic_schemes` collects every constructor and mapping
declaration out of a set of templates into one `PolySortScheme` per
declaration — `{ vars: Vec<TypeVarId>, sort: ResolvedSortId }` — keyed by
name into a `HashMap<String, Vec<PolySortScheme>>`. `Signature` carries this
table as a `schemes` field alongside `constructors`/`mappings`, so a name
lookup against a signature has exactly one place to look, not a separate
polymorphic table on the side:

- **The user-facing signature** (`ctx.signature`, built by
  `compute_signature`) gets `schemes` from *all six* container/function-update
  templates plus `BUILTIN_SCHEME_TEMPLATE`, via
  `build_polymorphic_schemes(ctx, CONTAINER_TEMPLATES.all().chain([&*BUILTIN_SCHEME_TEMPLATE]))`.
  A user specification's own declarations never carry a `type_var` block in
  current usage, so this only ever *adds* names to the signature rather than
  colliding with anything the user wrote.
- **A system equation's `builtin_schemes`** (`EquationRole::System`, see
  [the name-resolution table](system-specification.md#name-resolution-inside-a-system-equation))
  gets a narrower table from `build_builtin_scheme_signature`, built from
  `BUILTIN_SCHEME_TEMPLATE` alone — no container templates — for the same
  reason the old `BUILTIN_SCHEME_SIGNATURE` excluded them: a system
  equation's own group signature already carries the container operations as
  concrete overloads, so adding the polymorphic templates on top would create
  a spurious tie. `build_builtin_scheme_signature` memoizes its result on
  `TypeCheckContext::builtin_scheme_signature`, since the template it reads is
  process-wide, not per-equation.

## Instantiating a scheme

`ConstraintGenerator::instantiate_scheme` turns a `PolySortScheme`'s already-
interned `sort` into a fresh sort node for one occurrence: it walks the
`ResolvedSort` structurally, and every `Var(id)` it reaches becomes one fresh
unification variable, memoized in a local `HashMap<TypeVarId, InferSortId>`
so two occurrences of the same `id` within *this one instantiation* share the
same variable — the mechanism that makes `S` mean "the same `S`" on both
sides of `in: S # List(S) -> Bool`. A fresh `HashMap` is passed for every
call site in `gen_name`/`push_signature_disjuncts`, so distinct occurrences of
`in` in the same equation never share a variable with each other.

This replaces an older design where a template's sort variables were bare,
unresolved `Reference` nodes matched by name during instantiation — a
syntax-tree walk with no counterpart in the interned lattice. Because
`ResolvedTypeVar`/`ResolvedSort::Var` are resolved once, up front, alongside
every other sort, `instantiate_scheme` has no name-keyed path left to fall
back to: a scheme's `sort` can only ever contain `Var`, never a bare name.

## Real declaration spans for system-defined symbols

The bundled template files are registered into the shared `SourceMap` passed
to `DataSpecification::from_untyped_with` as virtual documents (e.g.
`<builtin>/list.mcrl2`), the same offsetting technique
[`merc_syntax::imports`](name-resolution.md) uses for `%import`. This is what
lets `TypeCheckContext::system_symbol_spans` — and so
[`ResolvedName::SystemDefined`'s `declaration`](typing-info.md) — carry a real,
renderable span for a system-defined constructor or mapping (`[]: List(S)`,
`in`, …) instead of `Span::default()`: hovering or jumping to one of these
symbols lands in the actual bundled `.mcrl2` source, not nowhere.

## Where this is headed

`PolySortScheme.vars` is not read anywhere yet — `instantiate_scheme`
currently discovers a scheme's bound variables structurally, by walking
`sort` and instantiating every `Var` it finds, rather than consulting
`vars`. It is kept for a planned next step: checking each template's own
defining equations *once*, with `vars` held rigid instead of instantiated
per call site, rather than the current per-instantiation-group re-checking
described in
[Why system equations can't share one pooled signature](system-specification.md#why-system-equations-cant-share-one-pooled-signature).
That step, and the open question of whether a user specification should ever
be allowed to declare its own `type_var` block, have not landed yet.
