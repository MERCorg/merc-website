# Lowering

Phase 4, the final phase of the pipeline, walks the typed representation
produced by [sort inference](sort-inference.md) and emits aterm
`merc_data::DataExpression`s, materializing the implicit coercions as explicit
function applications: numeric up-casts become the Appendix-B constructor
chains, and finite-to-unbounded container widenings become the corresponding
set/bag constructors. Number literals are lowered to their exact Appendix-B
constructor chains via arbitrary-precision binary encoding, and all binders
(`lambda`, `forall`/`exists`, set/bag comprehensions, `where`) are lowered too.
`DataSpecification::lower_data_specification` assembles the full
`Mcrl2DataSpecification` — user sorts, aliases, constructors, mappings and
equations, followed by the system-defined declarations and equations.

For a polymorphic container/function-update operation, lowering recovers the
concrete operation from the operator name together with the sort that
inference assigned the occurrence — see [the polymorphic
signature](system-specification.md#the-polymorphic-signature) for why
inference itself never resolves these to a concrete overload.

## Binary-aterm compatibility

The output schema is fixed by **binary-aterm compatibility**. merc must load
mCRL2's already type-checked binary specifications, and because the aterm
pool is maximally shared, a symbol the checker constructs must be
byte-for-byte identical to the same symbol read from a binary file, so that
the two share one pooled term. Already-typed binary input therefore bypasses
the checker entirely: both routes converge on the same
`merc_data::Mcrl2DataSpecification`, and downstream code is oblivious to the
provenance.

Lowering is invoked *after* `from_untyped` rather than inside it, so callers
that only need the typed intermediate representation pay nothing for the
aterm lowering.

## Known divergences from the mCRL2 toolset

merc's lowering matches the mCRL2 toolset's own C++ type checker term-for-term
for the overwhelming majority of specifications. This is checked mechanically
by `tools/mcrl2/crates/mcrl2/tests/lowering_conformance.rs`, which type checks
and lowers the same specification with both checkers and asserts structural
(address) equality of the resulting aterms in the shared, maximally-shared
aterm pool. Three cases are known to diverge, each in exactly one
`user_defined_*` section; the round-trip test for each such specification is
narrowed to the sections that do conform, rather than being dropped, so
everything else about the case stays guarded.

### Structured sorts

merc's `desugar_structured_sorts` turns `sort D = struct …;` into an abstract
sort `D` plus its constructor/recogniser/projection declarations, so `D`
lands in the *sorts* section. The toolset instead keeps the declaration as an
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

`normalize_sorts` erases alias names, and not only in the alias section
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
