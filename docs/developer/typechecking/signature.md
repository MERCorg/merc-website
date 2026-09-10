# Signature & Well-Typedness

Phase 2 of the pipeline computes the *signature* — the book's $(S, C, M)$ triple
(Definition 15.1.5): the declared sorts, constructors and mappings, resolved as
overload sets per name. While computing it, `build_signature` checks the
well-typedness conditions of Definition 15.1.7, and `resolve_sort` maps every
declaration-level sort expression onto the interned [`ResolvedSort`
lattice](sort-inference.md#the-sort-lattice) that the rest of the pipeline
shares.

## The `(S, C, M)` signature

`Signature` is a plain lookup table: each constructor/mapping name maps to a
`Vec<ResolvedSortId>`, one entry per overload — mCRL2 allows a name to be
declared more than once as long as the declarations are separated by sort or
arity, and duplicate declarations of the exact same symbol collapse into one
entry rather than two. `build_signature` is idempotent and memoized on
`TypeCheckContext`, so later phases all share one computed signature instead of
recomputing it.

## Polymorphic schemes

Alongside `constructors`/`mappings`, `Signature` carries a third, name-keyed
table, `schemes: HashMap<String, Vec<PolySortScheme>>`. A `PolySortScheme`
pairs a `ResolvedSortId` — built by `resolve_sort` from a template's own
declaration, so it may contain [`ResolvedSort::Var`](sort-inference.md#the-sort-lattice)
at any depth — with the `TypeVarId`s it binds. It is *not* a ground overload:
using one means instantiating it, substituting each bound variable for a
fresh unification variable (see
[the polymorphic signature](system-specification.md#the-polymorphic-signature)
for the container/function-update/comparison operators that populate this
table, and how instantiation works).

`schemes` is a separate table rather than a third `SignatureEntry` variant
folded into `constructors`/`mappings`: a scheme carries no
`ConstructorId`/`MapId` (it is synthesized from a template, not declared by
any user or system spec), so giving it the same shape as a ground overload
would mean threading an id that is never actually there. Keeping it additive
also meant every existing ground-overload consumer — `merge_signatures`,
`filter_signature`, the dedup in `push_overload`, every test that indexes
`signature.constructors`/`.mappings` — needed no change at all when this
table was introduced; only `build_signature`'s own construction and the one
lookup site in `gen_name`/`push_signature_disjuncts`
([inference.rs](system-specification.md#name-resolution-inside-a-system-equation))
needed to know it exists.

`schemes` is empty for almost every `Signature` value in the pipeline — a
user declaration never carries a `type_var` block (out of scope for now, see
`docs/polymorphism.md`'s "Open questions"), so it is populated only for the
one `Signature` merged into `ctx.signature` and the small standalone table a
system equation's own body consults; see
[the polymorphic signature](system-specification.md#the-polymorphic-signature)
for why those are two different tables rather than one.

## Well-typedness (Definition 15.1.7) { #well-typedness }

The checks split across two passes, at two different points in the pipeline,
because they need two different views of the specification:

- **`build_signature`**, run *before* alias normalization, rejects:
  - a product sort occurring anywhere but a function domain;
  - a constructor and a mapping sharing one name
    (`ConstructorAndMappingConflict`);
  - a zero-arity constant declared twice with different sorts
    (`DuplicateConstantDifferentSort`);
  - a name that redeclares a system-defined function
    (`SystemFunctionRedeclared`);
  - a constructor targeting a basic sort (`ConstructorForBasicSort`) or a
    function sort (`ConstructorForFunctionSort`).

  Running this *before* alias expansion means an error reports a sort exactly
  as the user wrote it — `D`, not whatever `D` expands to — which is why this
  pass, not [normalization](name-resolution.md#normalization), is where these
  checks live.

- **`is_well_typed`**, run *after* normalization, covers what's left — two
  checks that are not signature concerns and one that positively needs the
  normalized view:
  - **duplicate equation variables** — a `var` block declaring the same name
    twice is rejected outright, rather than silently letting the second
    declaration shadow the first the way by-name lookup during inference
    would;
  - **bare product sorts on an equation variable**, the same domain-only rule
    `build_signature` enforces for declarations;
  - **sort non-emptiness** — every sort with at least one constructor must be
    inhabited. `nonempty_sorts` computes this as a **least fixpoint**: it seeds
    the non-empty set with every sort that has *no* constructors at all
    (an abstract sort or an alias is unconstrained and assumed non-empty,
    along with every built-in, container and function-argument sort), then
    grows it by repeatedly admitting a constructor sort as soon as one of its
    constructors has every argument sort already in the set. A sort that never
    enters the set this way — every constructor of every reachable
    alternative recurses without a non-recursive base case — is rejected as
    `EmptySort`.

    This must run on the *normalized* specification specifically: a sort
    inhabited only through an alias (`sort D = Nat;`) would otherwise be
    misreported as empty, since the fixpoint needs `D` and `Nat` to already be
    the same sort by the time it runs.

## Sort resolution

Finally, `resolve_sort` maps every declaration-level `SortExpression` onto the
interned `ResolvedSort` lattice, memoized per `DefId` on
`ctx.sort_of_def`/`sort_of_constructor`/`sort_of_map` so a sort already
interned once is looked up rather than rebuilt. From this point on, sort
inference and lowering never touch a `SortExpression` again — every sort in
the pipeline is a small interned `ResolvedSortId`. See [Sort
Inference](sort-inference.md#the-sort-lattice) for the lattice itself and what
"interned" buys the rest of the pipeline.

## The system-defined specification

Alongside building the signature, Phase 2 also assembles the [system-defined
specification](system-specification.md) — the standard data types of Appendix
B (`Bool`, `Pos`, `Nat`, `Int`, `Real`, lists, sets, bags) injected for exactly
the sorts that occur in the specification. It is checked and resolved on its
own terms, separately from the rules above, for reasons that page explains in
detail.
