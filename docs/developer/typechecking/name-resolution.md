# Sort & Name Resolution

This page covers the first phases of the pipeline: the syntactic groundwork that
runs directly on the `merc_syntax` AST, before any sort is computed. Nothing
here depends on the signature or on inference.

## Phase 0 — Variable Name Resolution

Before any other phase runs, `resolve_data_specification_variables` rewrites
every `var`-block equation variable occurrence (`condition`/`lhs`/`rhs`) from a
plain `DataExprKind::Id(name)` into `DataExprKind::Resolved(name,
declaration_span)`, tying it to its own `var` declaration's span. Type checking
treats `Resolved` exactly like `Id`.

**Design decision — why a pre-pass, and why it can't fail.** A variable
occurrence's binder — `sum`/`dist`, a process's own parameters, a PBES/PRES
quantifier or equation parameter, a `lambda`/quantifier/comprehension/`whr`
binder — is decided purely by lexical scoping over the *untyped* syntax tree,
with no dependency on any inferred sort. That is what makes it different from
constructor/mapping resolution (which needs overload resolution against
argument sorts) or the arity-based action-vs-process disambiguation
`check_action_or_process` performs (see [Process
Specification](../specification/index.md#process-specification)) — both of those genuinely need type
checking to be underway. Because scoping alone answers "which binder does this
occurrence refer to", the pass needs no `DataSpecification` and cannot fail: a
name that resolves to nothing in scope is left as a plain `Id`, unresolved,
and later inference's `UndeclaredName` error is responsible for rejecting it if
it turns out to be genuinely undeclared.

## Phase 0 — The sort layer

The first real semantic phase establishes what sorts exist and rejects
malformed sort declarations, still operating directly on the AST rather than on
any interned representation.

### Name resolution

`resolve_sort_ids` assigns a definition id (`DefId`) to every `sort`
declaration, then every sort *reference* in the specification — including a
binder sort buried inside an equation body, such as a quantifier variable, not
just a declaration-level sort — is rewritten from `Reference(name)` to
`Resolved(name, DefId)`. Duplicate and undefined sort names are rejected, while
byte-identical duplicate declarations (`sort D; D;`) are silently accepted as
one.

### Alias checks

`check_aliases` rejects circular sort aliases with two separate searches, run
over the *resolved* declarations:

- **Circularity.** An alias may not reach itself through basic sorts,
  containers, or function sorts. A structured (`struct`) sort terminates the
  search instead of rejecting it, because recursion through a constructor is
  inductively well-founded — a `struct` can always be built from a
  non-recursive alternative first:

  ```mcrl2
  sort Tree = struct leaf | node(Tree, Tree);
  ```

  This is accepted: `Tree` is a `struct`, so the search stops there rather
  than unfolding `Tree` again inside `node`'s arguments.

- **Function-sort loops.** A second search continues *through* structured
  sorts as well, and rejects a cycle that passes through a function sort or an
  unbounded `Set`/`Bag` container even when a `struct` sits along the way:

  ```mcrl2
  sort S = struct f(S -> Bool);
  ```

  is rejected — `S` reaches itself through a function-sort argument, and a
  function sort has no cardinality-consistent interpretation for such a
  recursion. A loop through a `List`, `FSet`, or `FBag` container is fine,
  since those are inductively founded on the empty case the same way a
  `struct` alternative is.

### Normalization

`normalize_sorts` expands aliases to a canonical form: a non-structured alias
(`sort D = Nat;`, `sort L = List(D);`) is replaced by its recursively
normalized definition, so the alias and the sort it stands for become
indistinguishable and sort equality is structural throughout the rest of the
pipeline. A structured-sort alias instead stays a named representative — it
keeps its own name rather than being inlined — both because structured sorts
are identified by name (two structurally identical `struct`s are still
different sorts unless declared as the same name) and because expanding a
recursive `struct` definition would not terminate. A `visited` stack tracks
which aliases are currently being expanded, so an alias reached again during
its own expansion is kept as a named representative instead of unfolded
forever — this is what keeps normalization terminating on a cycle that closes
through an inline `struct` (which `check_aliases` permits, since recursion
through a constructor is well-defined) rather than diverging on it.

### Function-sort domain flattening

Function sorts with product domains such as `(A # B) -> C` are also flattened
here into a single multi-argument form `A # B -> C`, so that every later phase
sees one uniform representation of a function sort rather than having to
special-case a `Product` domain spine.
