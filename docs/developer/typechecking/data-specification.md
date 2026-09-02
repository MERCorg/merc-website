# Data Specification

This page covers the core pipeline sketched in the [overview](index.md): the
phases that turn an `UntypedDataSpecification` into a fully typed
`merc_data::Mcrl2DataSpecification`.

## Phase −1 — Variable go-to-definition (a syntactic pre-pass)

Before any of the phases below run, `resolve_data_specification_variables`
rewrites every `var`-block equation variable occurrence
(`condition`/`lhs`/`rhs`) from a plain `DataExprKind::Id(name)` into
`DataExprKind::Resolved(name, declaration_span)`, tying it to its own `var`
declaration's span. Type checking treats `Resolved` exactly like `Id` — this
pass only carries a declaration span alongside the existing by-name lookup, it
changes no resolution outcome — so this step is purely additive groundwork for
go-to-definition; see [LSP support](lsp.md) for the full picture, including the
matching passes over a process/PBES body.

## Phase 0 — The sort layer

The first phase establishes what sorts exist and rejects malformed sort
declarations, operating directly on the AST:

 - **Name resolution** assigns a definition id (`DefId`) to every `sort`
   declaration and rewrites each sort reference to point at its definition.
   Duplicate and undefined sort names are rejected, while byte-identical
   duplicate declarations are silently accepted as one.
 - **Alias checks** reject circular sort aliases, including cycles that only
   close through a function or container sort. A recursion that passes through
   a list is inductively well-founded (a list can be empty), but one that
   passes through a function sort or an unbounded set/bag is not, and is
   rejected.
 - **Normalization** expands aliases to a canonical form: non-structured
   aliases are inlined, while aliases of structured (`struct`) sorts stay as
   named representatives so that structurally identical structs share one sort.

Function sorts with product domains such as `(A # B) -> C` are also flattened
here into a single multi-argument form, so that later phases see one uniform
representation of a function sort.

## Phase 1 — Desugaring and operator lowering

Structured sorts (`struct` declarations) are desugared into an abstract sort
plus its constructors, recognisers and projection functions; anonymous inline
structs are first hoisted into fresh named declarations, with structurally
identical structs sharing one. The defining equations (recognisers,
projections, and the `==`/`<`/`<=` orderings) are generated into a
*system-defined* specification that accompanies the user's specification.

Built-in operator syntax is then lowered into plain applications — `x == y`
becomes `==(x, y)`, the list cons `[x]` becomes an application of the cons
operator, and so on — so that sort inference has a single application code path
instead of a special case for every operator. Number and container literals are
kept as dedicated nodes, because their sort is chosen by inference rather than
declared.

## Phase 2 — Signature and sort resolution

The *signature* query computes the book's $(S, C, M)$ triple — the declared
sorts, constructors and mappings — as resolved overload sets per name. While
computing it, the well-typedness conditions of Definition 15.1.7 are checked:
constructors and mappings must be disjoint, basic and function sorts may not
have constructors, and every sort with constructors must be non-empty. These
checks run *before* alias expansion so that errors refer to sorts as the user
wrote them; a syntactic safety net re-checks the normalized specification
afterwards.

The *system-defined* specification is assembled: the standard data types of
Appendix B (`Bool`, `Pos`, `Nat`, `Int`, `Real`, lists, sets, bags) are injected
for exactly the sorts that occur in the specification, computed as a transitive
fixed point (using `Set(S)` pulls in `FSet(S)`, and so on).

Finally, **sort resolution** maps every declaration-level sort expression onto
the interned `ResolvedSort` lattice described [below](#the-sort-lattice).

## The system-defined specification

The standard data types of Appendix B — `Bool`, `Pos`, `Nat`, `Int`, `Real`,
the `List`, `Set`, `Bag`, `FSet`, `FBag` containers, and function updates — are
not written by the user but are needed by almost every specification. merc keeps
them in a separate **system-defined specification**, assembled in Phase 2 for
exactly the sorts that occur (as the transitive fixed point above), alongside
the defining equations of the desugared structured sorts. It is *trusted,
generated content*: instantiated Appendix-B templates and generated struct
equations, not something a user typed.

### Why it is not type-checked as a user specification

It might seem natural to instantiate this specification for every sort that
occurs and then run the ordinary well-typedness checks and sort resolution over
it, exactly as for the user's declarations. merc deliberately does *not*, for
two reasons.

 - **It legitimately declares things a user may not.** The Appendix-B templates
   give the basic sorts their constructors (`@c0: Nat`, the `Pos`/`Int`/`Real`
   constructor chains) and use reserved `@`-prefixed names throughout. The
   well-typedness conditions of Definition 15.1.7 — no constructors on basic or
   function sorts, constructor/mapping disjointness — are *user*-facing rules
   that this generated content is meant to violate. Running them over the
   system specification would reject it out of hand.
 - **Instantiating it per sort *into the searchable signature* would create
   ambiguity.** The container and function-update operations (`in`, `#`, `|>`,
   `head`, the function-update operators, …) exist for *every* element sort.
   Resolving their per-sort instantiations into the signature — so
   `in: S # List(S) -> Bool` becomes one concrete overload for each `S` that
   occurs — while *also* keeping the polymorphic lookup below would list every
   such operation twice: once as the concrete overload and once polymorphically.
   A name with both a concrete and a polymorphic candidate for the same sort
   produces two tied disjuncts, which the solver reports as a spurious
   [ambiguity](#ranked-backtracking-search). (Full instantiation on its own,
   without the polymorphic lookup, would be fine — see [below](#the-polymorphic-signature).)

Instead, the system specification is trusted and checked separately, on its
own terms, in two passes with different jobs.

### Checking the system specification

`check_system_specification` runs first, unconditionally in every build — not
gated behind a `debug_assert!`, since silently trusting a malformed generated
spec in a release build would leave a rewrite specification quietly missing
rules. It is a cheap structural pass over the generated content exactly as
written, independent of any sort it happens to be instantiated for: every sort
reference is declared (catching an uninstantiated template variable like `S`),
product sorts occur only as function domains, no structured sort survives
desugaring, no `var` block declares a variable twice, every name in an
equation resolves (to a binder, an equation variable, a constructor or mapping,
or a builtin scheme), and the free variables of a condition and right-hand
side occur in the left-hand side, so every rule is executable by rewriting. It
exists to catch an editing mistake in a `spec/*.mcrl2` template cheaply, before
spending a full inference pass on it.

One signature-level rule from Phase 2's well-typedness check is re-checked
here too: no constructor may target a function sort
(`ConstructorForFunctionSort`). Of Definition 15.1.7's constructor-related
checks, this is the only one the system specification does not legitimately
break — no template declares a function-sort constructor, so a hit here
catches a genuine editing mistake. The other checks are deliberately *not*
shared, because the system specification is designed to break them:

 - `ConstructorForBasicSort` — the templates declare `@c0: Nat`,
   `@cNat: Pos -> Nat`, and similar constructors for the basic sorts,
   pervasively;
 - `DuplicateConstantDifferentSort` — `[]: List(S)` is a nullary polymorphic
   constructor, so a specification using `List(D)` and `List(E)` legitimately
   declares `[]` at two sorts once instantiated;
 - `ConstructorAndMappingConflict` — the same risk recurs across container
   instantiations.

`ConstructorForFunctionSort` is checked syntactically here — a raw walk over
the generated `SortExpression`s — rather than shared with `build_signature`'s
version of the same rule: the system specification is nominal and alias-free,
so no interned sort lattice is needed for it, and merging the two code paths
behind an `is_system` flag would be the flag-argument anti-pattern, since the
resolution mechanisms differ entirely (memoized user queries versus a raw
`resolve_system_sort` walk).

`check_system_equations` then runs full Phase-3 (constraint-based) inference
over every system equation, the same way `check_equations` does for user
equations — both share the same `ConstraintGenerator`/`Solver` (see
`EquationRole` in `inference.rs`), differing only in where a name or an
equation-variable sort resolves from: a system equation resolves against its
own group's `system_equation_signature_by_group` entry (see
`SystemEquationGroup`) rather than the full signature, and its sorts via
`resolve_system_sort` rather than `resolve_sort`. Signatures are scoped per
group, not pooled, because two instantiations of the same container template
(`Bag(Nat)`, `Bag(D)`) each carry a copy of its equations, and some of those
mention no argument pinning down which copy they belong to — one pooled
signature would make them ambiguous.

### The polymorphic signature

Because of the above, the built-in operators are made available to Phase-3
inference in three different ways, according to how many sorts they range over:

 - **Basic-sort operators** (`&&`, `+`, `-`, `*`, the ordering comparisons on
   numbers, …) range over the five basic sorts only. Their declarations *are*
   resolved per-sort onto the lattice, giving inference an ordinary finite
   overload set — the *system signature*.
 - **Comparison operators and `if`** (`==`, `!=`, `<`, `<=`, `>`, `>=`, `if`)
   exist for *every* sort and are never declared anywhere. They are typed as
   **schemes** — `==` as $?a \# ?a \to Bool$, `if` as $Bool \# ?a \# ?a \to ?a$
   — instantiated with a fresh unification variable per occurrence.
 - **Container and function-update operations** exist for every *element* sort.
   Their template declarations are collected once into a *polymorphic
   signature*, keyed by name, with the template sort variables (`S`, `T`) left
   as unresolved references. Inference looks them up there and instantiates each
   overload with fresh unification variables per occurrence, exactly like the
   comparison schemes.

This mirrors mCRL2's built-in polymorphic symbol table. The per-sort
instantiations of the polymorphic operations still exist in the system
specification — they are needed for the defining equations and for Phase-4
lowering — but, as explained above, they are deliberately *not* resolved into
the signature that inference searches. Phase-4 lowering recovers the concrete
operation from the operator name together with the sort that inference assigned
the occurrence.

Treating these operations polymorphically is ultimately an **optimization, not
a necessity**. merc could instead instantiate every polymorphic operation for
every element sort in the transitive fixed point — turning `in: S # List(S) ->
Bool` into concrete overloads `in: Nat # List(Nat) -> Bool`, `in: Pos #
List(Pos) -> Bool`, … — drop the polymorphic lookup, and resolve the results
into the ordinary signature like any user overload. That instantiation is
entirely possible and would accept exactly the same specifications. It is
avoided because it scales poorly: the set of element sorts grows with every
nested container, so each operation contributes one concrete overload per sort,
enlarging the disjunctions the solver must search at every use site. A single
template instantiated on demand with a fresh unification variable gives
inference one candidate — its element sort filled in from the arguments — where
full instantiation would give it many. The scheme also avoids pre-instantiating
an operation for an element sort that inference pins down only late (the element
of an empty `[]`, or one supplied by a default), and it keeps merc aligned with
mCRL2's own polymorphic built-in table. The ambiguity noted above is what
forbids doing *both* — instantiating *and* keeping the polymorphic lookup — not
what forces the polymorphic route on its own.

!!! note "One subtlety: arithmetic that is also a container operation"
    `+`, `-` and `*` are both number operators and the `Set`/`Bag` union,
    difference and intersection operators. When no user overload shadows such a
    name and it has no container reading at the use site, its numeric promotion
    is resolved by a single direct lookup rather than a disjunction over the
    basic-sort overloads — this keeps equations with many repeated arithmetic
    sub-expressions from branching combinatorially.

    When either condition fails — a user overload shadows the name, or the use
    site does have a container reading — the operator simply reverts to an
    ordinary `Disjunction`, exactly like any other overloaded name. The fast
    path is a common-case optimization, not a correctness fence: the
    [branch-and-bound pruning](#ranked-backtracking-search) and the
    argument-before-callee ordering still keep that fallback tractable, only
    without the direct-lookup savings.

### System-internal sorts and the DefId offset

Desugaring and instantiation introduce a few nominal sorts that the user never
declared — for example `@NatPair`, used by the number templates. These
*system-internal* sorts need identifiers on the same footing as the user's
sorts, whose names are keyed by a `DefId` (an index into the user's sort
declarations assigned during name resolution).

Rather than a second namespace, merc simply **continues the numbering**: a
system-internal sort declared at position $i$ in the system specification gets
the `DefId` $\mathit{user\_len} + i$, where $\mathit{user\_len}$ is the number
of user sort declarations. A `DefId` below `user_len` therefore indexes the
user declarations; one at or above it indexes the system-internal sorts, offset
by `user_len`. This keeps a resolved sort a single small index while letting a
name lookup fall through from the user table to the system table.

Because this offset is an *encoding* rather than a guaranteed contract, the two
directions of it live in one place: the assignment when the system signature is
resolved, and a single `TypeckContext::sort_name` accessor that performs the
reverse lookup for both debug rendering and Phase-4 lowering. No other pass
open-codes the `DefId − user_len` arithmetic, so a change to the scheme touches
exactly those two spots.

## The sort lattice

Sort inference works over an interned lattice of *resolved* sorts, which is the
vocabulary shared by unification and the solver. A `ResolvedSort` is one of:

 - a primitive sort (`Bool`, `Pos`, `Nat`, `Int`, `Real`);
 - a container sort `op(S)` such as `List(S)`, `Set(S)` or `FBag(S)`;
 - a function sort $A_0 \# \dots \# A_n \to B$;
 - a nominal sort `Def(d)`, identified by the declaration `d` it resolves to;
 - a `Unit` sort, used internally for the result of an action.

Because sorts are **interned**, each distinct sort is stored once and two sorts
are equal exactly when their indices are equal — a sort comparison is a single
integer comparison. Sub-sorts are stored as indices too, so a `ResolvedSort` is
small and structural equality never has to recurse.

Unlike the plain set of sorts in the book, these sorts form a **lattice** under
the sub-sort ordering that the implicit coercions define:

 - the number sorts form a chain $Pos \leq Nat \leq Int \leq Real$;
 - the finite containers embed into their unbounded counterparts,
   $FSet(S) \leq Set(S)$ and $FBag(S) \leq Bag(S)$, when the element sorts are
   equal;
 - all other distinct sorts are incomparable.

The lattice supplies a **join** (least common supersort) and **meet** (greatest
common subsort). A join is what lets two branches of an `if`, or the two sides
of an equation, meet at a single common sort: joining `Nat` and `Int` yields
`Int`, and joining `FSet(Pos)` and `Set(Pos)` yields `Set(Pos)`. This directly
models the numeric up-casting and container widening that the surface language
performs silently, but as a clean lattice operation rather than a collection of
special cases.

## Phase 3 — Sort inference

Sort inference runs **per equation** as a memoized query. Each equation is
typed independently, in two steps: constraint generation, then a ranked
backtracking search. The following three sections describe the machinery in
detail, since it is the heart of the crate.

### Constraint generation

The generator walks the lowered condition, left-hand side and right-hand side
of one equation and, for every sub-expression, allocates a *sort node* in the
unifier (see below) and emits constraints relating those nodes. Nodes are
numbered by an `ExprId` in a fixed order — parents before children, and within
an application the **arguments before the applied function**. This ordering
matters: by the time the solver reaches a function's overload choice, the
argument sorts are already known, so most overloads can be rejected immediately.

The constraint kinds are:

 - **Sub** — the sort of one node must be a sub-sort of another, modelling an
   implicit up-cast (a `Nat` argument passed where `Int` is expected). Equality
   is the special case where no coercion is needed.
 - **Lit** — a number literal must take a number sort admitting its kind (`0`
   is a natural, every other literal is positive). Literals prefer the most
   specific sort, so `1` is a `Pos` before it is widened.
 - **Disjunction** — a name with several overloads must resolve to exactly one
   of them. The solver commits to one disjunct per solution.
 - **Comprehension** — a set/bag comprehension `{ x: S | e }` reads as a
   `Set(S)` when its body is boolean and as a `Bag(S)` when its body is a
   number; the reading follows from the solved body sort.
 - **Numeric** — an application of an arithmetic operator (`+`, `-`, `*`, `/`,
   `div`, `mod`, `exp`, `max`, `min`) with no user overload. Because the
   built-in overloads of these operators never overlap on their argument sorts,
   at most one can match a fully-known argument tuple, so this is resolved by a
   direct lookup rather than by branching. Treating them this way — instead of
   as a general disjunction — is what keeps equations with many repeated
   arithmetic sub-expressions from blowing up combinatorially.
 - **Join** — a group of `Sub` constraints that all widen into the *same*
   shared sort variable (the operands of a comparison, the branches of an `if`,
   a set or bag element, the equation's two sides) is folded into one
   least-upper-bound over the lattice. Computing the common supersort in a
   single step avoids the order-sensitivity of solving the sub-constraints one
   at a time, where an early finite-container branch could otherwise fix the
   result prematurely and force the other branch to be re-explored.

Structural facts that must hold in *every* solution — that a callee has a
function sort, that a condition is boolean — are unified eagerly at generation
time, so a violation is reported as a direct error rather than a silent search
failure.

Equations whose binders use a sort that inference does not model yet (an
anonymous `struct`, a bare product) are left untyped rather than rejected, so
the rest of the specification still type checks.

### Unification with subtyping

Equality of sorts is decided by structural **unification** over a union-find
table. merc uses [`ena`](https://crates.io/crates/ena) — the Rust compiler's
extracted unification-table crate — for the union-find, wrapped in a `Unifier`
that adds an arena of sort nodes and the sub-sort operations.

A sort node under inference is one of: a fully resolved (interned) sort, a
container `op(subsort)` whose element may still contain variables, a function
sort whose parts may contain variables, or a bare **unification variable**. A
node like `List(?t)` — a list whose element sort `?t` is still unknown — is how
the generator represents an empty-list literal before the element sort is
pinned down.

Unification proceeds by the usual structural rules, with two additions specific
to this checker:

 - **Interning makes the base case trivial.** Two fully resolved sorts unify
   exactly when their indices are equal, so unification only ever spells out
   structure around the variables that remain.
 - **A resolved container or function sort unifies against a spelled-out one**
   by matching head constructors and recursing into the sub-sorts. This lets a
   half-known `List(?t)` unify with a fully resolved `List(Nat)` by binding
   `?t := Nat`.

Binding a variable runs an **occurs check** first, which rejects the infinite
sort a binding like `?t := List(?t)` would otherwise create.

Crucially, unification itself decides only **equality**, not sub-typing. The
sub-sort ordering is handled one level up, by the solver: unification never
silently widens `Nat` into `Int`. Instead, the `Unifier` exposes the strict
super-sorts and sub-sorts of a node — `Pos` yields `[Nat, Int, Real]`, `Real`
yields `[Int, Nat, Pos]` — in ascending distance, and only the head
constructor is widened (`Nat` has supersorts; `List(Nat)` does not). The solver
enumerates these candidates explicitly when a plain equality does not hold. This
separation keeps unification simple and total, and confines every coercion
decision to the ranked search where it can be measured and compared.

### Ranked backtracking search

The solver walks the constraints in generation order, and at each choice point
it tries the alternatives and recurses. Because inference must pick not just *a*
typing but the *best* one, every leaf of the search is scored by a lexicographic
**measure**, and the solver keeps the single best leaf:

 - each `Sub`, `Lit` and `Join` source contributes one measure component — `0`
   for an exact match, and a larger number for a wider coercion (the number of
   steps up the sub-sort chain);
 - components are ordered by generation position, earlier ones most
   significant, so a coercion high in the expression tree costs more than one
   deep inside it;
 - `Disjunction` and `Comprehension` contribute *no* component of their own but
   are explored exhaustively.

The minimum measure is the most specific typing: equality beats widening,
nearer widenings beat farther ones, and literals take their smallest admissible
sort. Each choice point does the same thing — **try equality first, then the
strict widenings in ascending distance** — so the first solution found down any
branch is already the locally cheapest.

Backtracking is implemented with the union-find table's native
**snapshot / rollback**. Before trying an alternative the solver snapshots the
variable bindings; if the branch dead-ends or is exhausted, it rolls back to
free exactly the variables bound since the snapshot. The sort-node arena is
append-only and is *not* rolled back — nodes created inside an abandoned branch
simply remain as harmless garbage — which keeps rollback to the cheap union-find
operation.

Two properties make the search both correct and tractable:

 - **Exhaustive disjunctions detect ambiguity.** Because every overload and
   every comprehension reading is explored, two distinct solutions that tie at
   the same minimum measure are reported as a genuine *ambiguity* error rather
   than silently picking one.
 - **Branch-and-bound pruning keeps it fast.** A partial branch whose measure
   prefix is already strictly worse, component for component, than the best leaf
   found so far can never win — earlier components dominate the lexicographic
   order — so it is cut immediately. Without this, an equation with many
   independent overloaded operators would explore every combination to its leaf;
   with it, the search stays practical. The pruning is *exact*: it changes only
   how much of the tree is visited, never which typing wins or which equations
   are ambiguous.

When the best leaf still leaves a sort variable free — an auxiliary sort that no
constraint ever pinned down, such as the element sort of an empty container that
is never used — the solver substitutes a default so the equation is accepted
rather than reported as underdetermined.

The inferred sorts are recorded in side tables mapping each expression to its
resolved sort and each name occurrence to the chosen overload, keyed by the
same `ExprId` numbering the generator used, ready for the lowering phase to
re-walk.

Because this global ranked search considers the whole equation at once, it
accepts some specifications that a purely local algorithm rejects as ambiguous —
for example resolving an overloaded call by ranking an exact match strictly
above one that needs a numeric up-cast, or typing a `where` clause by solving
all of its bindings jointly instead of one at a time.

### A worked example

Consider two overloads of the same name and a call that fits both:

```text
map  f: Nat -> Nat;
     f: Int -> Int;
var  n: Nat;
eqn  f(n) = n;
```

Generation numbers the argument `n` before the callee `f`, so by the time `f`'s
overload `Disjunction` is reached the argument sort is already known to be
`Nat`. Two disjuncts then unify:

 - `f: Nat -> Nat` — the argument `Nat` matches the parameter `Nat` exactly, so
   the argument's `Sub` contributes measure component `0`;
 - `f: Int -> Int` — the argument `Nat` must widen to `Int`, one step up the
   number chain, so the same `Sub` contributes `1`.

Both branches reach a leaf: the call type-checks either way. The measures differ
only in that argument component — `[…, 0, …]` versus `[…, 1, …]` — and because
`0 < 1` the exact `Nat -> Nat` overload wins. A plain "disjunction handed to
unification" would have no reason to prefer it; the measure is exactly what
rules out the needless up-cast.

The same ranking governs literals. In `f(n) = n`'s sibling `map g: Real; eqn g
= 1;`, the literal `1` is tried most-specific-first: `Pos` (generality `0`)
before `Nat`, `Int`, `Real`. `Pos` is consistent — it widens to `Real` at the
equation's join — so the leaf that types the literal itself as `Pos` and pays
the widening at the coercion point has a smaller measure than one that starts
the literal at `Real`. The literal is therefore typed `Pos` and coerced,
matching the rule that literals take their smallest admissible sort.

For a container example, `s == t` with `s: FSet(Pos)` and `t: Set(Pos)` shares
one variable `?a` between the operands. The `Join` computes the least upper
bound $FSet(Pos) \sqcup Set(Pos) = Set(Pos)$, charging one widening step to the
`FSet(Pos)` source and `0` to the already-`Set(Pos)` source — so both operands
agree on the least sort that admits them, `Set(Pos)`, and the comparison is
typed there.

## Phase 4 — Lowering

The final phase walks the typed representation and emits aterm
`merc_data::DataExpression`s, materializing the implicit coercions as explicit
function applications: numeric up-casts become the Appendix-B constructor
chains, and finite-to-unbounded container widenings become the corresponding
set/bag constructors. Number literals are lowered to their exact Appendix-B
constructor chains via arbitrary-precision binary encoding, and all binders
(`lambda`, `forall`/`exists`, set/bag comprehensions, `where`) are lowered too.
`DataSpecification::lower_data_specification` assembles the full
`Mcrl2DataSpecification` — user sorts, aliases, constructors, mappings and
equations, followed by the system-defined declarations and equations.

The output schema is fixed by **binary-aterm compatibility**. merc must load
mCRL2's already type-checked binary specifications, and because the aterm pool
is maximally shared, a symbol the checker constructs must be byte-for-byte
identical to the same symbol read from a binary file, so that the two share one
pooled term. Already-typed binary input therefore bypasses the checker
entirely: both routes converge on the same `merc_data::Mcrl2DataSpecification`,
and downstream code is oblivious to the provenance.

Lowering is invoked *after* `from_untyped` rather than inside it, so callers
that only need the typed intermediate representation pay nothing for the aterm
lowering.
