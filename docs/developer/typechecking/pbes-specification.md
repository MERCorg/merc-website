# PBES Specification

`PbesSpecification` is `ProcessSpecification`'s sibling for a parameterised
boolean equation system: it type checks a full `UntypedPbes` on top of the
same [data specification](data-specification.md) checker.
`PbesSpecification::from_untyped` first type checks the embedded data
specification exactly as `DataSpecification::from_untyped_with` does, then
resolves every `glob` variable's sort and every propositional-variable
equation's own parameter sorts, and finally walks every equation's formula and
`init` — resolving each `PropVarInst` by name and checking its argument count
and each argument's sort, checking `val(...)` expressions against `Bool`, and
scoping quantifier (`forall`/`exists`) binders to the subtree they bind.
Errors are reported as `PbesError`, a superset of
`WellTypedError`/`InferenceError`.

**Scope.** This checks *sorts and names* only: parameter/argument
sort-checking, propositional-variable name/arity resolution, quantifier-binder
scoping. It does **not** check PBES well-formedness properties like
monotonicity or alternation depth of propositional variables — those are a
separate semantic analysis, not type checking, and are out of scope here.

Unlike `ProcessSpecification`, there is no grammar-ambiguity reparse pass:
a PBES formula shares no tokens between two different readings the way a
process body's `Condition` does, so every `PbesExpr` the parser produces is
already correctly shaped.

`PbesSpecification::typing_info` exposes the same [span-keyed
`TypingInfo`](lsp.md) `DataSpecification`/`ProcessSpecification` do, merged
over every checked expression (a `val(...)` expression, a `PropVarInst`
argument, a quantifier binder) — computed once during the construction walk
above, so reading it back afterwards is a cheap clone rather than a second
pass.

## Declaration tables

`PbesSpecification` resolves a single-slot `name -> (parameters, ...)` table
for its propositional-variable equations, one entry per equation — unlike
`ProcessSpecification`'s `actions_by_name`/`processes_by_name` tables, which
map a name to a *list* of indices to support overload resolution. A PBES
equation is declared once each: `mu`/`nu X(...) = ...` re-declaring an already
-declared `X` is a `PbesError::DuplicatePropositionalVariable`, not an
overload, so there is no `NoMatchingOverload`/`AmbiguousActionOrProcess`
equivalent to report here — a `PropVarInst` either resolves to the one
declared equation or doesn't resolve at all.
