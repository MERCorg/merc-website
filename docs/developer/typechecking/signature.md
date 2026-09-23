# Signature & Well-Typedness

Phase 2 of the pipeline computes the *signature* — the book's $(S, C, M)$ triple
(Definition 15.1.5): the declared sorts, constructors and mappings, resolved as
overload sets per name. While computing it, Phase 2 checks the well-typedness
conditions of Definition 15.1.7, and maps every declaration-level sort
expression onto the interned [`ResolvedSort`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html)
[lattice](sort-inference.md#the-sort-lattice) that the rest of the pipeline
shares.

## The `(S, C, M)` signature

[`Signature`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html) is a plain lookup table: each constructor/mapping name maps to a
[`Vec`](https://doc.rust-lang.org/std/vec/struct.Vec.html) of [`ResolvedSortId`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/type.ResolvedSortId.html)s, one entry per overload — mCRL2 allows a name to be
declared more than once as long as the declarations are separated by sort or
arity, and duplicate declarations of the exact same symbol collapse into one
entry rather than two. Building it is idempotent and memoized on the checking
context, so later phases all share one computed signature instead of
recomputing it.

## Polymorphic schemes

Alongside [`constructors`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.constructors)/[`mappings`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.mappings), [`Signature`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html) carries a third, name-keyed
table, [`schemes`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.schemes), a [`HashMap`](https://doc.rust-lang.org/std/collections/struct.HashMap.html) from name to a [`Vec`](https://doc.rust-lang.org/std/vec/struct.Vec.html) of schemes. A [`PolySortScheme`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.PolySortScheme.html)
is a single-field wrapper around a [`ResolvedSortId`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/type.ResolvedSortId.html) —
`struct PolySortScheme { sort: ResolvedSortId }` — resolved from a template's own declaration, so it
may contain [`ResolvedSort::TypeVar`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.TypeVar) (see [the sort lattice](sort-inference.md#the-sort-lattice)) at any depth. It does *not*
separately store which [`TypeVarId`](https://mercorg.github.io/merc/merc_syntax/type.TypeVarId.html)s it binds: instantiation discovers them dynamically, by
walking the resolved sort tree and matching a [`ResolvedSort::TypeVar(id)`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.TypeVar) node wherever one occurs —
see [`instantiate_scheme`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.ConstraintGenerator.html#method.instantiate_scheme).
It is *not* a ground overload: using one means instantiating it, substituting each bound variable for a
fresh unification variable (see
[the polymorphic signature](system-specification.md#the-polymorphic-signature)
for the container/function-update/comparison operators that populate this
table, and how instantiation works).

[`schemes`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.schemes) is a separate table rather than a third `SignatureEntry` variant
folded into [`constructors`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.constructors)/[`mappings`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.mappings): a scheme carries no
[`ConstructorId`](https://mercorg.github.io/merc/merc_syntax/type.ConstructorId.html)/[`MapId`](https://mercorg.github.io/merc/merc_syntax/type.MapId.html) (it is synthesized from a template, not declared by
any user or system spec), so giving it the same shape as a ground overload
would mean threading an id that is never actually there. Keeping it additive
also meant every existing ground-overload consumer — signature merging and
filtering, overload deduplication, every test that indexes
[`signature.constructors`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.constructors)/[`.mappings`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.mappings) — needed no change at all when this table
was introduced; only signature construction itself and the one lookup site in
[inference](system-specification.md#name-resolution-inside-a-system-equation)
needed to know it exists.

[`schemes`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html#structfield.schemes) is empty for almost every [`Signature`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html) value in the pipeline — a
user declaration never carries a `type_var` block (out of scope for now, see
[what's still open](polymorphism.md)), so it is populated only for the
one [`Signature`](https://mercorg.github.io/merc/merc_typecheck/signature/signature/struct.Signature.html) merged into [`ctx.signature`](https://mercorg.github.io/merc/merc_typecheck/inference/context/struct.TypeCheckContext.html#structfield.signature) and the small standalone table a
system equation's own body consults; see
[the polymorphic signature](system-specification.md#the-polymorphic-signature)
for why those are two different tables rather than one.

## Well-typedness (Definition 15.1.7) { #well-typedness }

The checks split across two passes, at two different points in the pipeline,
because they need two different views of the specification:

- **The signature pass**, run *before* alias normalization, rejects:
  - a product sort occurring anywhere but a function domain;
  - a constructor and a mapping sharing one name
    ([`ConstructorAndMappingConflict`](https://mercorg.github.io/merc/merc_typecheck/enum.WellTypedError.html#variant.ConstructorAndMappingConflict));
  - a zero-arity constant declared twice with different sorts
    ([`DuplicateConstantDifferentSort`](https://mercorg.github.io/merc/merc_typecheck/enum.WellTypedError.html#variant.DuplicateConstantDifferentSort));
  - a name that redeclares a system-defined function
    ([`SystemFunctionRedeclared`](https://mercorg.github.io/merc/merc_typecheck/enum.WellTypedError.html#variant.SystemFunctionRedeclared));
  - a constructor targeting a basic sort ([`ConstructorForBasicSort`](https://mercorg.github.io/merc/merc_typecheck/enum.WellTypedError.html#variant.ConstructorForBasicSort)) or a
    function sort ([`ConstructorForFunctionSort`](https://mercorg.github.io/merc/merc_typecheck/enum.WellTypedError.html#variant.ConstructorForFunctionSort)).

  Running this *before* alias expansion means an error reports a sort exactly
  as the user wrote it — `D`, not whatever `D` expands to — which is why this
  pass, not [normalization](name-resolution.md#normalization), is where these
  checks live.

- **The well-typedness pass**, run *after* normalization, covers what's left —
  two checks that are not signature concerns and one that positively needs the
  normalized view:
  - **duplicate equation variables** — a `var` block declaring the same name
    twice is rejected outright, rather than silently letting the second
    declaration shadow the first the way by-name lookup during inference
    would;
  - **bare product sorts on an equation variable**, the same domain-only rule
    the signature pass enforces for declarations;
  - **sort non-emptiness** — every sort with at least one constructor must be
    inhabited. This is computed as a **least fixpoint**: the non-empty set is
    seeded with every sort that has *no* constructors at all
    (an abstract sort or an alias is unconstrained and assumed non-empty,
    along with every built-in, container and function-argument sort), then
    grows it by repeatedly admitting a constructor sort as soon as one of its
    constructors has every argument sort already in the set. A sort that never
    enters the set this way — every constructor of every reachable
    alternative recurses without a non-recursive base case — is rejected as
    [`EmptySort`](https://mercorg.github.io/merc/merc_typecheck/enum.WellTypedError.html#variant.EmptySort).

    This must run on the *normalized* specification specifically: a sort
    inhabited only through an alias (`sort D = Nat;`) would otherwise be
    misreported as empty, since the fixpoint needs `D` and `Nat` to already be
    the same sort by the time it runs.

## Sort resolution

Finally, every declaration-level [`SortExpression`](https://mercorg.github.io/merc/merc_syntax/type.SortExpression.html) is mapped onto the interned
[`ResolvedSort`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html) lattice, memoized per [`SortId`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/type.SortId.html) on the checking context
([`sort_of_def`](https://mercorg.github.io/merc/merc_typecheck/inference/context/struct.TypeCheckContext.html#structfield.sort_of_def)) so a sort
already interned once is looked up rather than rebuilt. From this point on, sort
inference and lowering never touch a [`SortExpression`](https://mercorg.github.io/merc/merc_syntax/type.SortExpression.html) again — every sort in
the pipeline is a small interned [`ResolvedSortId`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/type.ResolvedSortId.html). See [Sort
Inference](sort-inference.md#the-sort-lattice) for the lattice itself and what
"interned" buys the rest of the pipeline.

## The system-defined specification

Alongside building the signature, Phase 2 also assembles the [system-defined
specification](system-specification.md) — the five basic sorts' own Appendix-B
constructors, mappings and equations, plus the defining equations of the
desugared structured sorts. The container, function-update and comparison
operators are declared alongside it, in the very same signature, but as
polymorphic schemes rather than per-sort concrete declarations; only at
lowering time are they materialized for exactly the sorts a specification
actually uses. All of it is checked and resolved on its own terms, separately
from the rules above, for reasons that page explains in detail.
