# The System-Defined Specification

The standard data types of Appendix B — `Bool`, `Pos`, `Nat`, `Int`, `Real`,
the `List`, `Set`, `Bag`, `FSet`, `FBag` containers, and function updates — are
not written by the user but are needed by almost every specification. merc
keeps them in a separate **system-defined specification**, assembled in
[Phase 2](signature.md) for exactly the sorts that occur (as a transitive
fixed point — `Set(S)` pulls in `FSet(S)`, and so on), alongside the defining
equations of the [desugared structured sorts](desugaring.md). It is *trusted,
generated content*: instantiated Appendix-B templates and generated struct
equations, not something a user typed.

## Why it is not type-checked as a user specification

It might seem natural to instantiate this specification for every sort that
occurs and then run the ordinary well-typedness checks and sort resolution
over it, exactly as for the user's declarations. merc deliberately does *not*,
for two reasons.

- **It legitimately declares things a user may not.** The Appendix-B templates
  give the basic sorts their constructors (`@c0: Nat`, the `Pos`/`Int`/`Real`
  constructor chains) and use reserved `@`-prefixed names throughout. The
  well-typedness conditions of [Definition 15.1.7](signature.md#well-typedness)
  — no constructors on basic or function sorts, constructor/mapping
  disjointness — are *user*-facing rules that this generated content is meant
  to violate. Running them over the system specification would reject it out
  of hand.
- **Instantiating it per sort *into the searchable signature* would create
  ambiguity.** The container and function-update operations (`in`, `#`, `|>`,
  `head`, the function-update operators, …) exist for *every* element sort.
  Resolving their per-sort instantiations into the signature — so
  `in: S # List(S) -> Bool` becomes one concrete overload for each `S` that
  occurs — while *also* keeping the polymorphic lookup described
  [below](#the-polymorphic-signature) would list every such operation twice:
  once as the concrete overload and once polymorphically. A name with both a
  concrete and a polymorphic candidate for the same sort produces two tied
  disjuncts, which the solver reports as a spurious ambiguity. (Full
  instantiation on its own, without the polymorphic lookup, would be fine —
  see [below](#why-polymorphism-at-all).)

Instead, the system specification is trusted and checked separately, on its
own terms, in **two passes with two different jobs**: a cheap syntactic pass
that always runs, and a full inference pass, scoped per instantiation group.

## Two-stage checking

### Stage 1 — `check_system_specification` (cheap, unconditional, no inference)

This runs first, unconditionally, in every build — not gated behind a
`debug_assert!`, since silently trusting a malformed generated spec in a
release build would leave a rewrite specification quietly missing rules. It is
a purely structural pass over the generated content exactly as written,
independent of any sort it happens to be instantiated for:

- every sort reference is declared (catching an uninstantiated template
  variable like `S`), and every `Resolved` sort indexes a real user sort
  declaration;
- product sorts occur only as function domains, and no structured sort
  survives desugaring;
- no `var` block declares a variable twice;
- every name in an equation resolves — to a binder, an equation variable, a
  constructor or mapping of the system or user specification, or a builtin
  scheme (see [below](#the-polymorphic-signature));
- the free variables of a condition and right-hand side occur in the
  left-hand side, so every rule is executable by rewriting.

One signature-level rule from Phase 2's well-typedness check is re-checked
here too: no constructor may target a function sort
(`ConstructorForFunctionSort`). Of Definition 15.1.7's constructor-related
checks, this is the *only* one the system specification does not legitimately
break — no template declares a function-sort constructor, so a hit here always
catches a genuine editing mistake in a `spec/*.mcrl2` template. The other
checks are deliberately *not* shared, because the system specification is
designed to break them: `ConstructorForBasicSort` (`@c0: Nat`),
`DuplicateConstantDifferentSort` (`[]: List(S)` is nullary and polymorphic, so
using both `List(D)` and `List(E)` legitimately declares `[]` at two sorts once
instantiated), and `ConstructorAndMappingConflict` (the same risk recurs across
container instantiations).

`ConstructorForFunctionSort` is checked *syntactically* here — a raw walk over
the generated `SortExpression`s — rather than shared with `build_signature`'s
version of the same rule: the system specification is nominal and alias-free,
so no interned sort lattice is needed for it, and merging the two code paths
behind an `is_system` flag would be the flag-argument anti-pattern, since the
resolution mechanisms differ entirely (memoized user queries versus a raw
`resolve_system_sort` walk).

This stage exists to catch an editing mistake in a `spec/*.mcrl2` template
cheaply, before spending a full inference pass on it. It never runs Phase-3
sort inference.

### Stage 2 — `check_system_equations` (full inference, per instantiation group)

Once Stage 1 has confirmed the generated content is structurally sane,
`check_system_equations` runs the *same* Phase-3 constraint-based inference
over every system equation that `check_equations` runs for user equations —
both share the same `ConstraintGenerator`/`Solver` (`EquationRole` in
`inference.rs`). This is the stage most directly relevant to the question of
*how* system equations get their sorts, and it differs from user-equation
checking in two ways: **where names resolve from**, and **where sorts resolve
from**. This is the part covered in detail below.

## Why system equations can't share one pooled signature

Two instantiations of the same container template — say `Bag(Nat)` and
`Bag(D)` for some user sort `D` — each carry their **own copy** of the
template's defining equations. Some of those equations, like `bag.mcrl2`'s own
`@zero_ == @one_`, mention no argument at all: nothing about the equation's own
shape says whether it belongs to the `Nat` instantiation or the `D`
instantiation.

If both instantiations' declarations were resolved into one pooled signature,
type-checking that equation would find `@zero_`/`@one_` overloaded between the
`Bag(Nat)` and `Bag(D)` versions with no way to prefer one — a spurious
ambiguity in *generated* content, not a real ambiguity in anything the user
wrote. `SystemEquationGroup` exists to prevent exactly this:

- `build_system_defined_specification` generates the Appendix-B content as a
  worklist fixpoint (a container pulls in the containers it depends on: `Set(S)`
  needs `FSet(S)`, and so on), but keeps each *batch* of content generated for
  one concrete sort separate rather than merging it in immediately.
- Each batch is then partitioned by `container_group_key` — the sort **one
  level down** from the container (`Bag(Nat)`'s key is `Nat`; `FSet(Nat)`'s and
  `Set(Nat)`'s key is also `Nat`, so a container and its transitive
  dependencies share one group). This key is deliberately *not* recursive: a
  recursive key would collapse `FSet(Set(Nat))` onto the same key as an
  unrelated `Set(Nat)`, reintroducing exactly the ambiguity this grouping
  exists to prevent.
- Each partition becomes one `SystemEquationGroup`, recording its own
  `UntypedDataSpecification` slice and the `Range<usize>` of
  `equation_declarations` indices it occupies.
- `resolve_system_signature_full` then resolves each group's own constructor
  and mapping declarations into its **own** `Arc<Signature>`, stored at
  `ctx.system_equation_signature_by_group[eqn_spec_id]` — indexed by the
  equation-block id, so every equation in a given group's range shares the
  same signature.

So the `Bag(D)` group's `@zero_ == @one_` type-checks against a signature that
only contains `Bag(D)`'s own `@zero_`/`@one_`, and the `Bag(Nat)` group's copy
of the same equation sees only `Bag(Nat)`'s — the two never collide, because
they're never checked against the same signature at all.

Struct-desugaring equations follow the same rule for the same reason: `c1`
and `is_c1`, generated for `sort D = struct c1(pr1: Nat)?is_c1;`, are declared
on the *user* specification rather than the system one, but they still resolve
correctly because they land in their own group's own signature, not because
they're special-cased.

## Name resolution inside a system equation

Within `infer` (the shared Phase-3 entry point), an `EquationRole` selects
which signatures and polymorphic table a name resolves against. Both roles
share identical constraint generation, unification, and ranked search — only
the *lookup order* for a name, and *how* a declared sort resolves, differ:

| | User equation (`EquationRole::User`) | System equation (`EquationRole::System`) |
|---|---|---|
| Name resolution order | `ctx.signature` — ground overloads **and** its `schemes` table (container/function-update templates **and** the comparison/`if` schemes, merged into one table, see [below](#the-polymorphic-signature)) → `ctx.system_signature` (concretely-resolved basic-sort operators; its `schemes` is always empty) | `ctx.system_equation_signature_by_group[eqn_spec_id]` (**this equation's own group**, concretely resolved; its `schemes` is always empty too) → `ctx.system_signature` → `ctx.builtin_scheme_signature` (comparison/`if` schemes **only** — no container templates, built lazily by `build_builtin_scheme_signature`) |
| Declared-sort resolution | `resolve_sort` — through name resolution and the alias table | `resolve_system_sort` — via the pre-built `system_sort_ids` table, since the system spec's sort references never go through ordinary name resolution |
| Driven by | `check_equations` / `query_equation_typing` | `check_system_equations` / `query_system_equation_typing` |
| Memoized in | `ctx.equation_typing` | `ctx.system_equation_typing` |
| Contributes to `TypingInfo` | yes | no — a system equation has no source span in the user's document to attribute a typed node to |

### Why not just reuse `resolve_sort`?

The second row deserves its own justification: `resolve_sort` isn't merely
unoptimized for the system spec, it is structurally the wrong function to
call on it, for two independent reasons.

- **A system-spec sort reference was never resolved in the first place.**
  `resolve_sort`'s `Reference` arm is `unreachable!("Names must have been
  resolved")` — a hard precondition, not an oversight — because ordinary name
  resolution (`resolve_sort_ids`) runs exactly once, over the *user's* parsed
  AST, at the very start of the pipeline. The container and basic-sort
  templates (`list.mcrl2`, `bag.mcrl2`, …) are parsed *separately*, straight
  from bundled `.mcrl2` files, and merged in only afterwards — well after that
  one resolution pass has already run and moved on. Their `S`/`T` sort
  variables are genuinely still bare `Reference` nodes at that point
  (`replace_sort` later does a pure syntactic find-and-replace on them, not a
  resolution), so handing one to `resolve_sort` would simply panic.
- **Even a `Resolved` node in the system spec can point at the wrong
  specification.** Instantiating a template for a user sort (substituting `D`
  for `S` in the `List` template, say) splices in the user sort's own
  already-`Resolved("D", id)` node, where `id` indexes
  `user_spec.sort_declarations`. `query_sort_of_def` — which `resolve_sort`
  delegates to — asserts that `id` indexes *the exact `spec` argument passed
  to it*. Calling `resolve_sort(ctx, system, ...)` on that node would look up
  `system.sort_declarations[id]`: a different, unrelated `Vec` that merely
  *numbers* its own system-internal sorts (`@NatPair`, …) starting where the
  user's leaves off (see [below](#system-internal-sorts-and-the-defid-offset))
  — a convention for the `DefId` encoding, not a literal shared array, so
  indexing into the wrong `Vec` with it is either out of bounds or silently
  wrong.

`resolve_system_sort` exists specifically to bridge both gaps: its
`Reference` case checks the system-internal `system_sort_ids` table first,
then falls back to a by-name search over `user_spec.sort_declarations` —
needed because generated source such as `structured_sort_equations`'s struct
equations is *re-parsed from scratch*, so a user sort it mentions by name is
a fresh `Reference` too, never touched by the user's own resolution pass even
though that same sort already has a `DefId` from when the user spec was
resolved. Its `Resolved(_, id)` case always redirects to
`query_sort_of_def(ctx, user_spec, id)` — the *user* spec, unconditionally,
regardless of which spec the reference itself lives in.

A more radical alternative — splice the system spec's declarations into the
user's own `sort_declarations` and run `resolve_sort_ids` once over the
combination, so one ordinary resolver would do — isn't available, because the
system spec isn't a fixed, complete AST at the point resolution would need to
happen: it's generated incrementally, as a worklist fixpoint discovering which
containers are needed, and only *after* the user spec is already fully
resolved (instantiation needs to know which concrete sorts occur to
substitute). Splicing new declarations into the user's own `Vec` after the
fact would invalidate anything already memoized against that `Vec`'s identity,
and would blur the "trusted, generated, checked on its own terms" boundary the
whole design leans on — the one that keeps `@c0: Nat`-style
constructors-for-basic-sorts from tripping the user-facing well-typedness
rules in the first place.

The row that matters most for understanding the "special handling" is the
first one: **why does a system equation get a *narrower* polymorphic table
than a user equation does?**

Within a group, a container/function-update operation like `in` or `|>` is
already present as a **concrete, resolved overload** in that group's own
signature — e.g. `in: Nat # List(Nat) -> Bool` when checking the `List(Nat)`
group's equations, resolved by `resolve_system_signature_full` exactly the way
a user's own declaration would be. If `EquationRole::System` also consulted
the *polymorphic* container table (`POLYMORPHIC_SIGNATURE`), a call to `in`
inside that equation would get **two** disjuncts for the same occurrence — the
concrete group overload, and a freshly-instantiated polymorphic template
instance — which unify to the same sort and so tie at the same minimum
measure, reported as a spurious ambiguity. This is the *same* failure mode
described [above](#why-it-is-not-type-checked-as-a-user-specification) for why
the outer signature never resolves the polymorphic operations concretely
either; it just resurfaces one level down, inside the group's own equations,
if left unguarded.

The comparison operators and `if` don't carry this risk, for either role: they
are never declared concretely *anywhere* — no template ever writes `==: Nat #
Nat -> Bool` as an ordinary mapping — so the *only* way to reach them, in a
user equation or a system one, is through the scheme table. That's why
`BUILTIN_SCHEME_SIGNATURE` — the same `POLYMORPHIC_SIGNATURE` minus its six
container templates — is exactly what a system equation is given: everything
that has no concrete counterpart anywhere stays reachable, and everything that
does (the container/function-update operations) is reached through the
concrete group signature instead, never both ways at once.

## The polymorphic signature { #the-polymorphic-signature }

Because of the above, the built-in operators are made available to Phase-3
inference in two different ways, according to how many sorts they range over:

- **Basic-sort operators** (`&&`, `+`, `-`, `*`, the ordering comparisons on
  numbers, …) range over the five basic sorts only. Their declarations *are*
  resolved per-sort onto the lattice, giving inference an ordinary finite
  overload set — the *system signature* (`ctx.system_signature`).
- **Comparison operators and `if`** (`==`, `!=`, `<`, `<=`, `>`, `>=`, `if`)
  and **container/function-update operations** (`in`, `#`, `|>`, `head`, the
  function-update operators, …) both exist for every sort (respectively,
  every element sort) and are never declared concretely anywhere. Both are
  typed as **schemes** — `==` as $?a \# ?a \to Bool$, `if` as $Bool \# ?a
  \# ?a \to ?a$, `in` as $?a \# List(?a) \to Bool$ — each declared exactly
  once, in a template with a real `type_var` block: `spec/*.mcrl2`'s six
  container/function-update templates, and `BUILTIN_SCHEME_TEMPLATE` for the
  comparisons and `if`. `build_polymorphic_schemes` turns every declaration
  of every such template into a [`PolySortScheme`](signature.md#polymorphic-schemes)
  by resolving it with the ordinary `resolve_sort` — legal here specifically
  because none of these templates references a `DefId`/nominal sort (see
  [below](#why-resolve_sort-is-safe-on-a-template)). Every occurrence of a
  template's own bound variable interns to the *same* `ResolvedSort::Var`,
  which is what lets `S` mean "the same `S`" on both sides of a scheme like
  `in: S # List(S) -> Bool`.

Using a scheme means *instantiating* it: `ConstraintGenerator::instantiate_scheme`
walks the scheme's already-interned `ResolvedSort` — not a syntax tree —
substituting one fresh unification variable for each distinct `Var` it
encounters, shared across that `Var`'s occurrences within the one call. This
mirrors mCRL2's own polymorphic built-in symbol table. The per-sort
instantiations of the container/function-update operations still exist
*concretely* in the system-defined specification — needed for their own
defining equations (via the group signatures above) and for Phase-4 lowering
— but, as explained above, they are deliberately *not* resolved into the
*outer* signature a user equation's inference searches; only the scheme is.
Phase-4 lowering recovers the concrete operation from the operator name
together with the sort inference assigned the occurrence.

### One merged table for a user equation, a narrower one for a system equation

`ctx.signature.schemes` — built once, alongside the ordinary `constructors`/
`mappings`, by `build_signature` — holds *all* of the above together:
containers, function-update, and the comparison/`if` schemes, in the one
`Signature` a user equation's `gen_name` already searches for its ground
overloads. This is why a user equation needs only two lookups, not three:
`push_signature_disjuncts` pushes both the ground and the scheme overloads of
`ctx.signature` in one pass, then does the same (ground only — its `schemes`
is always empty) for `ctx.system_signature`.

A system equation cannot reuse `ctx.signature.schemes` wholesale, for the same
reason [above](#why-system-equations-cant-share-one-pooled-signature) that it
cannot reuse the container instantiations concretely: its own group signature
already resolves the container/function-update operations *concretely*, for
its own group, so re-adding the polymorphic container schemes as a fallback
would misreport ambiguity — every container-op call in a system equation
would tie between the group's concrete overload and a freshly-instantiated
scheme of the same sort. The comparison operators and `if` carry no such
risk — no template ever declares `==: Nat # Nat -> Bool` concretely, so they
are reachable *only* through a scheme, for either role. This asymmetry is why
a system equation is handed a different, narrower table,
`ctx.builtin_scheme_signature`: built lazily by `build_builtin_scheme_signature`
from `BUILTIN_SCHEME_TEMPLATE` alone (no container templates), and consulted
by `gen_name` as one small extra loop after the two `push_signature_disjuncts`
calls above.

`ctx.builtin_scheme_signature` and `ctx.signature.schemes` are populated by
the *same* function, `build_polymorphic_schemes`, just handed a different
list of templates — one instantiation mechanism for the whole crate, not two.
Before this, `BUILTIN_SCHEME_TEMPLATE` was the last template anywhere that
still spelled its variable as a bare `Reference("S")` rather than a
`type_var` block, matched by name at every call site
(`template_instance`/`template_node`, walking the raw `SortExpression`
syntax tree per occurrence, one fresh `HashMap<String, InferSortId>` per
call); giving it a real `type_var` — the same as the six container templates
already had — retired that string-matching path entirely, along with the
`POLYMORPHIC_SIGNATURE`/`BUILTIN_SCHEME_SIGNATURE` `LazyLock` statics that
used to hold the old syntax-tree-shaped tables. They could not simply become
fields on `ctx` unchanged, either: a `PolySortScheme`'s `ResolvedSortId` is
scoped to one `TypeCheckContext`'s own `SortInterner`, so — unlike the old
`Reference`-based tables, which needed no interner at all to build — the
replacement can only be built once per `ctx`, never once per process as a
`static` would imply.

### Why `resolve_sort` is safe to call on a template { #why-resolve_sort-is-safe-on-a-template }

`resolve_sort` ordinarily panics on a `Reference` node (see
[below](#why-not-just-reuse-resolve_sort)) and, for a `Resolved` node,
indexes whichever spec's `sort_declarations` was passed in — a real risk when
a system-internal `DefId` is involved (see [the `DefId`
offset](#system-internal-sorts-and-the-defid-offset)). Neither risk applies
to the six container/function-update templates or `BUILTIN_SCHEME_TEMPLATE`:
none of them declares a nominal `sort X;` or contains a `Resolved(_, DefId)`
node anywhere — only `type_var`, primitive, container and function sorts — so
`resolve_sort` never reaches a `Reference` or `Resolved` arm on this path at
all. `build_polymorphic_schemes` calls `resolve_sort(ctx, template,
&decl.sort)` against each template's own self-contained spec exactly because
this was verified, not assumed — the same property is what let migration-plan
step 3 of `docs/polymorphism.md` (the RFC behind this design) scope itself to
exactly this set of templates and stop there, leaving
`ctx.system_signature`/`resolve_system_sort`/`SystemEquationGroup`/
`EquationRole` untouched: the basic-sort operators' own declarations *do*
reference system-internal nominal sorts like `@NatPair`, so retiring
`resolve_system_sort` in their favor needs the `DefId`-collision problem
solved first, a separable piece of work the migration plan tracks as its own
later step.

### Why polymorphism at all

Treating these operations polymorphically is ultimately an **optimization,
not a necessity**. merc could instead instantiate every polymorphic operation
for every element sort in the transitive fixed point — turning `in: S #
List(S) -> Bool` into concrete overloads `in: Nat # List(Nat) -> Bool`, `in:
Pos # List(Pos) -> Bool`, … — drop the polymorphic lookup, and resolve the
results into the ordinary signature like any user overload. That
instantiation is entirely possible and would accept exactly the same
specifications. It is avoided because it scales poorly: the set of element
sorts grows with every nested container, so each operation contributes one
concrete overload per sort, enlarging the disjunctions the solver must search
at every use site. A single template instantiated on demand with a fresh
unification variable gives inference one candidate — its element sort filled
in from the arguments — where full instantiation would give it many. The
scheme also avoids pre-instantiating an operation for an element sort that
inference pins down only late (the element of an empty `[]`, or one supplied
by a default), and it keeps merc aligned with mCRL2's own polymorphic built-in
table. The ambiguity noted above is what forbids doing *both* —
instantiating *and* keeping the polymorphic lookup — not what forces the
polymorphic route on its own.

!!! note "One subtlety: arithmetic that is also a container operation"
    `+`, `-` and `*` are both number operators and the `Set`/`Bag` union,
    difference and intersection operators, so their `Disjunction` includes
    the basic-sort overloads *and* the polymorphic container templates
    together — the container reading is simply one more disjunct, ruled out
    like any other by the argument sorts.

    `merc_typecheck` used to special-case the arithmetic-family names (`+`,
    `-`, `*`, `/`, `div`, `mod`, `exp`, `max`, `min`) with a direct-lookup
    fast path that skipped building a `Disjunction` for them entirely, to
    keep equations with many repeated arithmetic sub-expressions from
    branching combinatorially — see
    `test_repeated_arithmetic_stays_tractable`
    (`crates/typecheck/tests/inference_test.rs`) for the regression shape
    that motivated it. It was removed: `+`/`-`/`*` could never actually take
    it (they always have the container reading above, so the fast path was
    permanently unavailable for exactly the three names most likely to
    repeat in an equation), and measuring the other six names directly
    against the plain `Disjunction` path showed the
    [branch-and-bound pruning](sort-inference.md#ranked-backtracking-search)
    already keeps repeated arithmetic tractable on its own — a nine-level
    nested equation with eighteen `+`/`*` occurrences type checks in a
    couple of milliseconds either way. The fast path's own bookkeeping cost
    more than the modest constant factor it saved.

## System-internal sorts and the `DefId` offset

Desugaring and instantiation introduce a few nominal sorts that the user never
declared — for example `@NatPair`, used by the number templates. These
*system-internal* sorts need identifiers on the same footing as the user's
sorts, whose names are keyed by a `DefId` (an index into the user's sort
declarations assigned during name resolution).

Rather than a second namespace, merc simply **continues the numbering**: a
system-internal sort declared at position $i$ in the system specification gets
the `DefId` $\mathit{user\_len} + i$, where $\mathit{user\_len}$ is the number
of user sort declarations. A `DefId` below `user_len` therefore indexes the
user declarations; one at or above it indexes the system-internal sorts,
offset by `user_len`. This keeps a resolved sort a single small index while
letting a name lookup fall through from the user table to the system table.

Because this offset is an *encoding* rather than a guaranteed contract, the
two directions of it live in one place: the assignment when the system
signature is resolved (`build_system_sort_ids`), and a single
`TypeCheckContext::sort_name` accessor that performs the reverse lookup for
both debug rendering and Phase-4 lowering. No other pass open-codes the
`DefId − user_len` arithmetic, so a change to the scheme touches exactly those
two spots.
