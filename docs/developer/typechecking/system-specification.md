# Phase 3: The System-Defined Specification

The standard data types of Appendix B — `Bool`, `Pos`, `Nat`, `Int`, `Real`,
the `List`, `Set`, `Bag`, `FSet`, `FBag` containers, and function updates — are
not written by the user but are needed by almost every specification. merc
keeps them apart from the user's own declarations in two ways, at two
different times:

- **[`DataSpecification`](https://mercorg.github.io/merc/merc_typecheck/data_specification/struct.DataSpecification.html)'s own [`system`](https://mercorg.github.io/merc/merc_typecheck/data_specification/struct.DataSpecification.html#structfield.system) field**, assembled once in
  [Phase 2](signature.md) and checked eagerly, holds only the five basic
  sorts' own constructors/mappings/equations (`basics`) plus the defining
  equations of the [desugared structured sorts](desugaring.md) — never a
  container or function-update instantiation.
- **The container, function-update and comparison operations** (`in`, `#`,
  `|>`, `head`, the function-update operators, `==`, `<`, `if`, …) are
  declared exactly once, polymorphically, as
  [schemes](#the-polymorphic-signature) in the one pooled signature every
  declaration lives in. Their *ground* instantiations — `in: Nat # List(Nat)
  -> Bool` and the equations that define it — are never part of `system` at
  all; they are generated on demand, only for the sorts that actually occur,
  at [Phase 4 lowering](lowering.md), the one point where the checker has to
  hand a rewriter concrete symbols instead of a scheme.

That split is why `system` is small: what used to be "every Appendix-B
declaration for every sort in the fixed point" is now "the handful of things
that are checked once, eagerly, because a rewriter needs concrete content
built from them later." [Type Variables & Polymorphic Schemes](polymorphism.md)
covers how a scheme is declared, resolved and instantiated; this page covers
why the split exists at all, and how each side of it is checked.

## Why it is not type-checked as a user specification

It might seem natural to resolve `basics` and the desugared structs' own
equations as ordinary user content and be done with it. merc almost does —
see [below](#checking-system-basics-and-desugared-structs) — but two things
keep even this smaller `system` from being *identical* to a user
specification.

- **It legitimately declares things a user may not.** The basic-sort
  templates give `Nat`/`Pos`/`Int`/`Real` their constructor chains
  (`@c0: Nat`, …) and use reserved `@`-prefixed names throughout. The
  well-typedness conditions of [Definition 15.1.7](signature.md#well-typedness)
  that forbid a constructor on a basic sort are *user*-facing rules this
  generated content is meant to violate on purpose.
- **A user declaration may not shadow it.** A reserved-name check runs before
  `basics` is even merged in, and rejects any user `cons`/`map`
  declaration that reuses a basic-sort symbol's name, any of the polymorphic
  operator names (container, function-update or comparison), or the reserved
  `@` prefix — unconditionally, not just when the sorts happen to collide.
  This is what keeps the one pooled signature from ever having to decide
  whether a user's own `map in: ...` is a second overload of the built-in
  scheme `in` or a hard conflict with it: the question never comes up,
  because the declaration that would raise it is rejected first.

Both are handled the same way for the container/function-update/comparison
operations too, just earlier: the names Appendix-B's own templates declare
feed that same reserved-name check, and those operations are never resolved
into the signature as *concrete* overloads at all (only as schemes, see
[below](#the-polymorphic-signature)), so there is no per-sort
concrete/polymorphic pair for the same name to tie against each other the way
an earlier design risked.

## Checking `system`: basics and desugared structs { #checking-system-basics-and-desugared-structs }

Once `basics` and the desugared structs' own equations are assembled, `system`
is checked through almost the same pipeline a user's own declarations are,
not a bespoke one:

- **Sort references resolve through the one shared resolver.** `basics`'s and
  the re-parsed struct equations' own bare sort names (`@NatPair`, a struct's
  own field sorts, …) are resolved by the same pass that resolves the user's
  own sort names, against the one shared
  `sorts` table — see [System-internal sorts](#system-internal-sorts) below
  for why there is no second table or offset convention to reason about here.
- **Equation well-formedness is checked again, directly, over `system`'s own
  equations** — the same duplicate-`var`-block-variable, bare-product-sort-on-a-variable
  and free-variable-occurs-on-lhs rules
  [well-typedness](signature.md#well-typedness) already applied to the user's
  own equations. Neither rule has a trusted-content
  exemption — a generated equation with an unbound right-hand-side variable is
  just as unexecutable by rewriting as a user one — so there is nothing for a
  `trusted` flag to gate here, unlike the next bullet.
- **`basics`'s constructor/mapping declarations go through the same
  signature-layer checks the user's own declarations do, as `trusted`
  content.**
  `trusted` skips exactly one rule, [`ConstructorForBasicSort`](https://mercorg.github.io/merc/merc_typecheck/signature/is_well_typed/enum.WellTypedError.html#variant.ConstructorForBasicSort) (`@c0: Nat` and
  friends); every other 15.1.7 signature check (no constructor for a function
  sort, constructor/mapping disjointness, no zero-arity symbol under two
  different sorts) runs unconditionally, catching a real bug in a bundled
  `.mcrl2` template rather than letting it through as "generated, so
  presumably fine."
- **Full Phase-3 inference runs over every `system` equation**, the same
  constraint generation, unification and ranked search that drives user
  equations — see
  [Name resolution inside a system equation](#name-resolution-inside-a-system-equation)
  for the one thing that differs, which signature and builtin-scheme table a
  name resolves against.

Nothing here needs an unconditional, inference-free structural safety net the
way the [generated container
content](lowering.md#materializing-ground-content-at-lowering-time) does: `system` is a fixed,
finite AST assembled once, and every rule above either runs the exact code a
user declaration's own well-typedness already trusts, or is a real check
against generated content that would otherwise sail through unnoticed
(the signature-layer checks over `basics`).

## Name resolution inside a system equation

Within the shared Phase-3 entry point, an [`EquationRole`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.EquationRole.html) selects
where a binder/equation-variable's declared sort resolves from and which spec
an [`EqnSpecId`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/type.EqnSpecId.html) indexes into — it does **not** select which signature a name
resolves against. [`User`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.EquationRole.html#variant.User), [`System`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.EquationRole.html#variant.System) and
[`Template`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.EquationRole.html#variant.Template) all resolve every name, in the same order, against the same
single pooled [`ctx.signature`](https://mercorg.github.io/merc/merc_typecheck/inference/context/struct.TypeCheckContext.html#structfield.signature) — every user declaration, `basics`'s own
operators, and every container/function-update/comparison scheme — with every
candidate visible unfiltered, and share identical constraint generation,
unification and ranked search. Neither of the generated roles needs a
narrower table of its own: there is no separate scheme table for
struct-scoped system equations, and a template is checked with its own
scheme already merged into that signature unconditionally. Declared-sort
resolution is shared the same way, memoized per
([`EquationRole`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.EquationRole.html), [`VarId`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/type.VarId.html)).

Where the roles diverge is in how the resulting equation typing is computed,
stored, and fed back. `User` and `System` equations are both inferred per
equation — but for `System` that covers only `system`'s own basics and
desugared-struct equations. The Appendix-B container/function-update/comparison
blocks a [`TemplateInstantiation`](https://mercorg.github.io/merc/merc_typecheck/lowering/instantiate/struct.TemplateInstantiation.html) covers skip inference
entirely: they were already [proven once per
template](polymorphism.md#checking-a-templates-equations-once-rigidly) when
`Template` checked them, and each instantiation site just substitutes that proven typing
straight into [`ctx.system_equation_typing`](https://mercorg.github.io/merc/merc_typecheck/inference/context/struct.TypeCheckContext.html#structfield.system_equation_typing) — the
same table `System` inference itself populates, so that table ends up filled
by two disjoint routes rather than by inference alone. Otherwise each role
memoizes into its own table: [`ctx.equation_typing`](https://mercorg.github.io/merc/merc_typecheck/inference/context/struct.TypeCheckContext.html#structfield.equation_typing) for `User`,
`ctx.system_equation_typing` for `System`, and
[`ctx.template_typings`](https://mercorg.github.io/merc/merc_typecheck/inference/context/struct.TypeCheckContext.html#structfield.template_typings) for `Template`. And only `User` contributes to
[`TypingInfo`](https://mercorg.github.io/merc/merc_typecheck/typing_info/struct.TypingInfo.html), since neither a system equation nor a template's has
a source span in the user's document to attribute a typed node to.

## The polymorphic signature { #the-polymorphic-signature }

The built-in operators reach Phase-3 inference in two different ways,
according to how many sorts they range over:

- **Basic-sort operators** (`&&`, `+`, `-`, `*`, the ordering comparisons on
  numbers, …) range over the five basic sorts only. Their declarations *are*
  resolved concretely, giving inference an ordinary finite overload set,
  merged directly into the one pooled [`ctx.signature`](https://mercorg.github.io/merc/merc_typecheck/inference/context/struct.TypeCheckContext.html#structfield.signature) alongside the user's
  own declarations — there is no separate table for them once merging is
  done.
- **Comparison operators and `if`** (`==`, `!=`, `<`, `<=`, `>`, `>=`,
  `less_total`, `if`) exist for *every* sort and are never declared concretely
  anywhere. They are typed as schemes — `==` as $\forall S.\ S \# S \to Bool$,
  `if` as $\forall S.\ Bool \# S \# S \to S$ — built once from
  [`BUILTIN_SCHEME_TEMPLATE`](https://mercorg.github.io/merc/merc_typecheck/signature/standard_sorts/static.BUILTIN_SCHEME_TEMPLATE.html). `less_total` is not user-facing: it is a total
  order on `S` that `Set`/`Bag`/`FSet`/`FBag` use internally to keep their
  element lists canonically sorted even for a sort whose `<` is not itself
  total (e.g. a `Set` ordered by subset).
- **Container and function-update operations** exist for every *element*
  sort. Their template declarations, each with its own explicit `type_var`
  block, are collected once into [`Signature::schemes`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.schemes), keyed by name — see
  [Type Variables & Polymorphic Schemes](polymorphism.md) for exactly how a
  `type_var S;` block resolves and
  how a scheme is instantiated fresh, with a new unification variable, at
  each occurrence.

This mirrors mCRL2's own polymorphic built-in symbol table. Concrete,
per-sort instantiations of these operations are never resolved into
[`ctx.signature`](https://mercorg.github.io/merc/merc_typecheck/inference/context/struct.TypeCheckContext.html#structfield.signature) at all — only into the generated content
[lowering builds](lowering.md#materializing-ground-content-at-lowering-time) on demand,
which is never itself re-resolved into a signature, only lowered directly.

### Why polymorphism at all

Treating these operations polymorphically is not only a performance
optimization, but required.

A first approach would be to instead fully instantiate every polymorphic
operation for every element sort that occurs — turning `in: S # List(S) -> Bool`
into concrete overloads `in: Nat # List(Nat) -> Bool`, `in: Pos # List(Pos) ->
Bool`, … — and resolve the results into the ordinary signature like any user
overload, dropping the scheme lookup entirely. However, pooling every
instantiation's generated declarations into one flat signature means two
instantiations of the same template collide under the same names (`[]: List(D)`
and `[]: List(E)`, `@zero_: Bag(Nat)` and `@zero_: Bag(D)`, …), so checking one
instantiation's own generated equations can pick up an unrelated instantiation's
declaration as a spurious extra overload and misreport a well-typed equation as
ambiguous.

The scheme-based design removes the need for this. A template's equations are
proven exactly once against an unresolved type variable (see [Checking a
template's equations once,
rigidly](polymorphism.md#checking-a-templates-equations-once-rigidly)), and every concrete
instantiation is produced afterward purely by substitution, at [lowering
time](lowering.md#materializing-ground-content-at-lowering-time) — never
independently inferred. There is never more than one instantiation's
declarations in play during checking, so there is nothing left to collide, and
no per-instantiation scoping is needed to prevent it.

## System-internal sorts { #system-internal-sorts }

Desugaring and instantiation introduce a few nominal sorts the user never
declared — `@NatPair`, used by the number templates, is the main example.
These are folded directly into [`spec.sort_declarations`](https://mercorg.github.io/merc/merc_syntax/struct.UntypedDataSpecification.html#structfield.sort_declarations), the same table the
user's own sort declarations live in, before the one-time sort-resolution pass
ever runs — so `@NatPair` gets an
ordinary [`SortId`](https://mercorg.github.io/merc/merc_syntax/type.SortId.html) from that same pass, findable by name exactly like a user
sort, with no second namespace, no offset arithmetic, and no reverse lookup to
keep in sync anywhere. A [`SortId`](https://mercorg.github.io/merc/merc_syntax/type.SortId.html) means "index into the one table," everywhere,
unconditionally, and a name lookup in [`spec.sort_declarations`](https://mercorg.github.io/merc/merc_syntax/struct.UntypedDataSpecification.html#structfield.sort_declarations) works the same
way for a user sort and a system-internal one alike.

## Loading system-defined content into the source map { #loading-system-defined-content-into-the-source-map }

The system-defined declarations are registered into the same
[`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html)
the user's own files were parsed into (see [Source Maps &
Imports](../parsing/source_map.md)), as *virtual* sources with synthetic
names such as `<builtin>/nat.mcrl2` or `<builtin>/list.mcrl2`. This is why
building a [`DataSpecification`](https://mercorg.github.io/merc/merc_typecheck/data_specification/struct.DataSpecification.html)
takes a `&mut` [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html)
rather than creating its own: pass the one the specification was parsed (and
`%import`-resolved) against, so a diagnostic or a go-to-definition query can
point into system-defined content just as it points into a user file. A
convenience wrapper over a throwaway [`SourceMap`](https://mercorg.github.io/merc/merc_utilities/source_map/struct.SourceMap.html)
exists for callers that never render a span (most tests).

Only the content that ends up in a concrete specification is registered —
`basics`, as part of [`system`](https://mercorg.github.io/merc/merc_typecheck/data_specification/struct.DataSpecification.html#structfield.system),
and the per-concrete-sort content instantiated at [lowering
time](lowering.md#materializing-ground-content-at-lowering-time). The bare
parse that [`CONTAINER_TEMPLATES`](https://mercorg.github.io/merc/merc_typecheck/signature/standard_sorts/static.CONTAINER_TEMPLATES.html)
and [`BUILTIN_SCHEME_TEMPLATE`](https://mercorg.github.io/merc/merc_typecheck/signature/standard_sorts/static.BUILTIN_SCHEME_TEMPLATE.html)
are built from, which feeds [`Signature::schemes`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.schemes),
is never registered and its spans are meaningless against any source map. A
registered copy reuses that bare AST — cloned, then shifted into its
registration's base offset — rather than parsing the text a second time.

While [checking `system`](#checking-system-basics-and-desugared-structs), the
declaration span of every constructor and mapping is recorded in
[`system_symbol_spans`](https://mercorg.github.io/merc/merc_typecheck/inference/context/struct.TypeCheckContext.html#structfield.system_symbol_spans),
keyed by `(name, `[`ResolvedSortId`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/type.ResolvedSortId.html)`)`.
[LSP support](typing-info.md#lsp-support) falls back to this table for an
operator that is not one of the user's own declarations, reporting it as
[`ResolvedName::SystemDefined`](https://mercorg.github.io/merc/merc_typecheck/typing_info/enum.ResolvedName.html#variant.SystemDefined)
with a real location inside the relevant `<builtin>/*.mcrl2` document.
Container, function-update and comparison operators (`in`, `head`, `==`, …)
are resolved as [schemes](polymorphism.md) instead and are not in this table,
so they currently report `declaration: None`.
