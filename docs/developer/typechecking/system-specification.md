# The System-Defined Specification

The standard data types of Appendix B — `Bool`, `Pos`, `Nat`, `Int`, `Real`,
the `List`, `Set`, `Bag`, `FSet`, `FBag` containers, and function updates — are
not written by the user but are needed by almost every specification. merc
keeps them apart from the user's own declarations in two ways, at two
different times:

- **[`DataSpecification`](https://mercorg.github.io/merc/merc_typecheck/data_specification/struct.DataSpecification.html)'s own `system` field**, assembled once in
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
way the generated container content described next does: `system` is a fixed,
finite AST assembled once, and every rule above either runs the exact code a
user declaration's own well-typedness already trusts, or is a real check
against generated content that would otherwise sail through unnoticed
(the signature-layer checks over `basics`).

## Checking the container templates: once, rigidly

A container/function-update template (`list.mcrl2`, `set.mcrl2`, …) is parsed
once, with its own `type_var S;` block, and never re-parsed per instantiation.
Its constructor/mapping declarations become [`PolySortScheme`](#the-polymorphic-signature)
entries in the one pooled signature; its own defining equations —
`bag.mcrl2`'s `@zero_ == @one_`, and the rest — are checked exactly **once**,
with the template's type variable(s) held **rigid**: a skolem constant, not a
unification variable, for the duration of that one check. This happens
unconditionally while a [`DataSpecification`](https://mercorg.github.io/merc/merc_typecheck/data_specification/struct.DataSpecification.html) is built, regardless of whether the
specification being checked ever uses a container at all, and the result — a
[`TemplateCheck`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.TemplateCheck.html) per template, `{ type_vars, typings }` — is memoized on the
checking context.

Rigidity is what makes checking once sound, the same "generalize, then
instantiate fresh at each use" discipline let-polymorphism relies on: proving
an equation holds for an arbitrary, unconstrained `S` entails it holds for
every particular `S` a caller later substitutes, so `@zero_ == @one_` need
never be checked again for `Bag(Nat)`, `Bag(D)`, or any other concrete
instantiation. A user specification using several different container
element sorts pays this cost exactly once per template, not once per element
sort — see [Why polymorphism at all](#why-polymorphism-at-all) for the
tradeoff this embodies more broadly.

A multi-argument function update (arity > 1) has no single bundled template —
the checker builds and checks a generic one for whichever arities actually
occur, the first time each is seen, temporarily merging its own scheme into the
pooled signature for the duration of that one check (its
`@func_update`/`@is_not_an_update`/… names would otherwise fail to unify
against an arity it wasn't declared for) and caching the result under
`"function_update_{arity}"`, the same table the bundled templates use.

## Materializing ground content at lowering time

Container/function-update/comparison operations stay schemes for as long as
type checking runs — see [Why it is not type-checked as a user
specification](#why-it-is-not-type-checked-as-a-user-specification) for why
concrete overloads are never resolved into the signature alongside them. A
rewriter has no representation for a scheme, though: [lowering](lowering.md)
needs concrete constructors, mappings and equations for exactly the container,
function-update and comparison instantiations the specification actually
uses. It builds them fresh, once, for that call:

- **A syntactic pass** walks a worklist fixpoint over
  `spec`'s own textual sort occurrences (a `Set(S)` pulls in `FSet(S)`; a
  function sort pulls in the function-update operators for its arity), and
  independently, uniformly, over *every* sort for the comparison operators.
  For each sort it discovers, it clones the matching template's declarations
  and equations and **substitutes** the concrete sort for the template's bound
  type variable — a syntactic substitution walk over the template's own AST,
  not a fresh parse and not a fresh resolution pass: the substituted sort node
  is already a resolved `Resolved(name, DefId)` node, copied in from the user's
  own already-resolved sort tree.
- **A second, inference-driven pass** catches what that syntactic scan cannot
  see: the element sort of a `List`/`Set`/`Bag` enumeration literal
  (`[1, 2, 3]`, `{1, 2}`) or a bare numeral is never written down anywhere in
  the source — it is purely a product of Phase-3 inference — so this replays
  the same worklist against every sort that shows up in an already-typed
  equation's own inferred sorts, diffed against what the syntactic pass
  already covered.
- **Each generated equation is then specialized from its template's
  already-proven, rigid typing by substitution — one [`TemplateInstantiation`](https://mercorg.github.io/merc/merc_typecheck/lowering/instantiate/struct.TemplateInstantiation.html)
  per generated block — instead of re-running inference.** This is the same
  "prove once, specialize by substitution" step described
  [above](#checking-the-container-templates-once-rigidly), applied at the point
  the specialization is actually needed. Two
  instantiations of the same template (`Bag(Nat)`, `Bag(D)`) never collide the
  way an earlier design's grouping machinery had to guard against, because
  neither one is independently *inferred* at all — there is nothing left to
  tie or disambiguate.
- **One unconditional, inference-free structural safety net remains**, run
  once over the generated content
  merged with `system` (so a generated equation referencing a basic-sort
  operator by name resolves correctly). Nothing else ever checks this
  content's own names and sort references — substitution, not inference,
  produced it — so this stays a raw, syntactic walk: every sort reference is
  declared and every `Resolved` node indexes a real sort declaration; no `var`
  block declares a variable twice; the free variables of a condition and
  right-hand side occur in the left-hand side; and no constructor targets a
  function sort (the one 15.1.7 signature rule this generated content does
  *not* legitimately break — a hit here is always a bug in a `spec/*.mcrl2`
  template, not a false positive). It deliberately does **not** re-check
  constructor/mapping disjointness or duplicate-constant-different-sort: `[]:
  List(D)` and `[]: List(E)` are meant to both exist once both sorts occur,
  the same intentional exemption the pre-lowering signature never had to make
  because these declarations were never resolved into it at all. Should never
  fail for a well-formed template — a failure here is a bug in the generator,
  not in anything the user wrote, so it panics rather than threading a
  `Result` through lowering.

## Name resolution inside a system equation

Within the shared Phase-3 entry point, an [`EquationRole`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.EquationRole.html) selects
which signature and builtin-scheme table a name resolves against, and where a
binder/equation-variable's declared sort resolves from. All three roles share
identical constraint generation, unification and ranked search:

| | User ([`EquationRole::User`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.EquationRole.html#variant.User)) | `system` equation ([`EquationRole::System`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.EquationRole.html#variant.System)) | Container template's own equations ([`EquationRole::Template`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.EquationRole.html#variant.Template)) |
|---|---|---|---|
| Name resolution order | `ctx.signature` (the full pooled signature — every user declaration, `basics`'s own operators, and every container/function-update/comparison scheme) | This equation's own `ctx.struct_signature_overrides` entry if it belongs to a struct, else `ctx.basics_signature` (basic-sort operators only) → the narrow builtin-scheme table (comparison/`if` schemes **only**, never the container templates) | `ctx.signature`, exactly as `User` — checked with the template's own scheme already present in it, since signature construction merges every template's scheme in unconditionally |
| Declared-sort resolution | memoized per [`VarId`](https://mercorg.github.io/merc/merc_syntax/syntax_tree/type.VarId.html) | unmemoized | unmemoized |
| Equation typing | inferred per equation | inferred per equation, or specialized by substitution when a [`TemplateInstantiation`](https://mercorg.github.io/merc/merc_typecheck/lowering/instantiate/struct.TemplateInstantiation.html) covers the block | inferred once, rigidly, per template |
| Memoized in | `ctx.equation_typing` | `ctx.system_equation_typing` | `ctx.template_typings` |
| Contributes to [`TypingInfo`](https://mercorg.github.io/merc/merc_typecheck/typing_info/struct.TypingInfo.html) | yes | no — a system equation has no source span in the user's document to attribute a typed node to | no |

The `System` row's struct-scoped override exists for the same reason it
always has: a struct's own recogniser/projection/comparison equations must
resolve `is_c1`/`pr1`/`==` against *that struct's own* constructors and
projections, not the rest of the user's specification — an unrelated struct's
same-named field would otherwise leak in as a spurious extra overload. It is
built once per struct, while the [`DataSpecification`](https://mercorg.github.io/merc/merc_typecheck/data_specification/struct.DataSpecification.html) is constructed, by
filtering the full signature down to that struct's own constructor/mapping
names and merging in the basic-sort operators.

The `System` role deliberately never falls back to the full `ctx.signature`
the way `User`/`Template` do — doing so would let a struct's own equations (or
`basics`'s own) see every user declaration, not just the handful of names
they actually need. `builtin_schemes` is correspondingly narrow for the same
reason: only the comparison/`if` schemes, never the six container templates,
because `system` never itself calls a container operation.

## The polymorphic signature { #the-polymorphic-signature }

The built-in operators reach Phase-3 inference in two different ways,
according to how many sorts they range over:

- **Basic-sort operators** (`&&`, `+`, `-`, `*`, the ordering comparisons on
  numbers, …) range over the five basic sorts only. Their declarations *are*
  resolved concretely, giving inference an ordinary finite overload set —
  `ctx.basics_signature`, merged into the one pooled `ctx.signature` too.
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
`ctx.signature` at all — only into the generated content
[lowering builds](#materializing-ground-content-at-lowering-time) on demand,
which is never itself re-resolved into a signature, only lowered directly.

### Why polymorphism at all

Treating these operations polymorphically is ultimately an **optimization,
not a necessity**. merc could instead fully instantiate every polymorphic
operation for every element sort that occurs — turning `in: S # List(S) ->
Bool` into concrete overloads `in: Nat # List(Nat) -> Bool`, `in: Pos #
List(Pos) -> Bool`, … — and resolve the results into the ordinary signature
like any user overload, dropping the scheme lookup entirely. That
instantiation is entirely possible and would accept exactly the same
specifications; it just used to be how merc worked, before this scheme-based
representation replaced it. It remains the wrong default because it scales
poorly: the set of element sorts grows with every nested container, so each
operation would contribute one concrete overload per sort, enlarging the
disjunctions the solver must search at every use site. A single template
instantiated on demand with a fresh unification variable gives inference one
candidate — its element sort filled in from the arguments — where full
instantiation would give it many. The scheme also avoids pre-instantiating an
operation for an element sort that inference pins down only late (the element
of an empty `[]`, or one supplied by a default), and it keeps merc aligned
with mCRL2's own polymorphic built-in table.

!!! note "One subtlety: arithmetic that is also a container operation"
    `+`, `-` and `*` are both number operators and the `Set`/`Bag` union,
    difference and intersection operators, so their [`Disjunction`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.Disjunction.html) includes
    the basic-sort overloads *and* the polymorphic container templates
    together — the container reading is simply one more disjunct, ruled out
    like any other by the argument sorts.

    `merc_typecheck` used to special-case the arithmetic-family names (`+`,
    `-`, `*`, `/`, `div`, `mod`, `exp`, `max`, `min`) with a direct-lookup
    fast path that skipped building a [`Disjunction`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.Disjunction.html) for them entirely, to
    keep equations with many repeated arithmetic sub-expressions from
    branching combinatorially — see the repeated-arithmetic regression test
    in the typecheck crate's inference tests for the shape that motivated it.
    It was removed: `+`/`-`/`*` could never actually take it (they always have
    the container reading above, so the fast path was
    permanently unavailable for exactly the three names most likely to
    repeat in an equation), and measuring the other six names directly
    against the plain [`Disjunction`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.Disjunction.html) path showed the
    [branch-and-bound pruning](sort-inference.md#ranked-backtracking-search)
    already keeps repeated arithmetic tractable on its own — a nine-level
    nested equation with eighteen `+`/`*` occurrences type checks in a
    couple of milliseconds either way. The fast path's own bookkeeping cost
    more than the modest constant factor it saved.

## System-internal sorts { #system-internal-sorts }

Desugaring and instantiation introduce a few nominal sorts the user never
declared — `@NatPair`, used by the number templates, is the main example.
These are folded directly into `spec.sort_declarations`, the same table the
user's own sort declarations live in, before the one-time sort-resolution pass
ever runs — so `@NatPair` gets an
ordinary `DefId` from that same pass, findable by name exactly like a user
sort, with no second namespace, no offset arithmetic, and no reverse lookup to
keep in sync anywhere. A `DefId` means "index into the one table," everywhere,
unconditionally, and a name lookup in `spec.sort_declarations` works the same
way for a user sort and a system-internal one alike.
