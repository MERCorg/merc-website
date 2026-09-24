# Lowering

This step walks the typed representation produced by [sort
inference](sort-inference.md) and emits aterm
[`merc_data::DataExpression`](https://mercorg.github.io/merc/merc_data/struct.DataExpression.html)s,
materializing the implicit coercions as explicit function applications: numeric
up-casts become the Appendix-B constructor chains, and finite-to-unbounded
container widenings become the corresponding set/bag constructors. Number
literals are lowered to their exact Appendix-B constructor chains via
arbitrary-precision binary encoding, and all binders (`lambda`,
`forall`/`exists`, set/bag comprehensions, `where`) are lowered too. The phase
assembles the full
[`Mcrl2DataSpecification`](https://mercorg.github.io/merc/merc_data/struct.Mcrl2DataSpecification.html).

## Materializing ground content at lowering time

For a polymorphic container/function-update operation, lowering recovers the
concrete operation from the operator name together with the sort that
inference assigned the occurrence — see [the polymorphic
signature](system-specification.md#the-polymorphic-signature) for why
inference itself never resolves these to a concrete overload. Container,
function-update and comparison operations stay schemes for as long as type
checking runs, and a rewriter has no representation for a scheme: lowering
needs concrete constructors, mappings and equations for exactly the container,
function-update and comparison instantiations the specification actually uses.
It builds them fresh, once, for that call:

- **A syntactic pass** walks a worklist fixpoint over
  [`spec`](https://mercorg.github.io/merc/merc_typecheck/data_specification/struct.DataSpecification.html#structfield.spec)'s own textual sort occurrences (a `Set(S)` pulls in `FSet(S)`; a
  function sort pulls in the function-update operators for its arity), and
  independently, uniformly, over *every* sort for the comparison operators.
  For each sort it discovers, it clones the matching template's declarations
  and equations and **substitutes** the concrete sort for the template's bound
  type variable — a syntactic substitution walk over the template's own AST,
  not a fresh parse and not a fresh resolution pass: the substituted sort node
  is already a resolved [`Resolved`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.Resolved)`(name, `[`SortId`](https://mercorg.github.io/merc/merc_syntax/type.SortId.html)`)` node, copied in from the user's
  own already-resolved sort tree.
- **A second, inference-driven pass** catches what that syntactic scan cannot
  see: the element sort of a `List`/`Set`/`Bag` enumeration literal
  (`[1, 2, 3]`, `{1, 2}`) or a bare numeral is never written down anywhere in
  the source — it is purely a product of Phase-3 inference — so this replays
  the same worklist against every sort that shows up in an already-typed
  equation's own inferred sorts, diffed against what the syntactic pass
  already covered.
- **Each generated equation is then specialized from its template's
  already-proven typing by substitution — one [`TemplateInstantiation`](https://mercorg.github.io/merc/merc_typecheck/lowering/instantiate/struct.TemplateInstantiation.html)
  per generated block — instead of re-running inference.** This is the same
  "prove once, specialize by substitution" step described in [Checking a
  template's equations once,
  rigidly](polymorphism.md#checking-a-templates-equations-once-rigidly),
  applied at the point the specialization is actually needed. Two
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
  declared and every [`Resolved`](https://mercorg.github.io/merc/merc_syntax/enum.SortExpressionKind.html#variant.Resolved) node indexes a real sort declaration; no `var`
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
  [`Result`](https://doc.rust-lang.org/std/result/enum.Result.html) through lowering.

## Binary-aterm compatibility

The output schema is fixed by **binary-aterm compatibility**. merc must load
mCRL2's already type-checked binary specifications, and because the aterm
pool is maximally shared, a symbol the checker constructs must be
byte-for-byte identical to the same symbol read from a binary file, so that
the two share one pooled term. Already-typed binary input therefore bypasses
the checker entirely: both routes converge on the same
[`merc_data::Mcrl2DataSpecification`](https://mercorg.github.io/merc/merc_data/struct.Mcrl2DataSpecification.html), and downstream code is oblivious to the
provenance.

Lowering is invoked *after* type checking rather than inside it, so callers
that only need the typed intermediate representation pay nothing for the aterm
lowering.

## Known divergences from the mCRL2 toolset

merc's lowering matches the mCRL2 toolset's own C++ type checker term-for-term
for the overwhelming majority of specifications. This is checked mechanically
by a conformance test that type checks and lowers the same specification with
both checkers and asserts structural
(address) equality of the resulting aterms in the shared, maximally-shared
aterm pool. Three cases are known to diverge, each in exactly one
`user_defined_*` section; the round-trip test for each such specification is
narrowed to the sections that do conform, rather than being dropped, so
everything else about the case stays guarded.

### Structured sorts

merc's [desugaring](desugaring.md) turns `sort D = struct …;` into an abstract
sort `D` plus its constructor/recogniser/projection declarations, so `D` lands
in the *sorts* section. The toolset instead keeps the declaration as an
alias `D = SortStruct(…)` and leaves its sorts section empty. Every symbol
the struct declares, and any equation using it, do conform — only the sorts
section differs.

```mcrl2
sort D = struct c1(pr1: Nat, pr2: Bool)?is_c1 | c2?is_c2;
map f: D -> Bool;
var d: D;
eqn f(d) = is_c1(d);
```

The recursive case (`sort Tree = struct leaf | node(left: Tree, right:
Tree);`) is checked the same way, since the recursion is what makes the
constructor and equation terms worth checking separately.

### Canonical sort representatives

[Normalization](name-resolution.md#normalization) erases alias names, and not
only in the alias section
(`sort B = A;` becomes `B = Nat` once `A = Nat`) — every *use* of the alias is
expanded too, so a mapping declared as `C -> Bool` lowers with `List(Nat)`
where the toolset keeps the name `C`:

```mcrl2
sort A = Nat; B = A; C = List(B);
sort D;
cons d: D;
map f: C -> Bool; g: D -> Bool;
var x: D;
eqn g(x) = true;
```

Only the sections that never mention an alias round-trip: the abstract sort
`D` and its own constructor and equation. The alias *declaration* itself is
fine when there is no indirection to expand.

### Expected-sort propagation

Consider a `where` binding with no expected sort:

```mcrl2
map f: Nat -> Nat;
var x: Nat;
eqn f(x) = y + y whr y = x + 1 end;
```

Both checkers pick the exact overload `+: Nat # Pos -> Pos` for `x + 1`,
binding `y: Pos`. The body `y + y` then has expected sort `Nat`: the toolset
*pushes that expectation down* into the choice of `+`, picking `+: Nat # Nat
-> Nat` and wrapping *both* operands in `Pos2Nat`. merc instead types the
body at its own minimal sort, `Pos`, and widens the result once at the end.
Both readings are well-sorted — only the toolset's is what the binary aterm
form holds, so it is the one lowering must match.

The minimal reproduction drops the `where` entirely:

```mcrl2
map f: Nat -> Nat;
var x: Nat;
eqn f(x) = x + 1;
```

With `x: Nat` and the equation's expected sort `Nat`, the toolset resolves
`+` at its result sort — `+: Nat # Nat -> Nat`, retyping the literal `1` at
`Nat` — while merc's ranked search prefers the overload needing no widening
at all, `+: Nat # Pos -> Pos`, and widens the result to `Nat` afterwards.
Only the equations section can see the difference; sorts, aliases,
constructors and mappings are untouched.
