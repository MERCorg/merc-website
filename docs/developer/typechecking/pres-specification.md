# PRES Specification

`PresSpecification` is `PbesSpecification`'s sibling for a parameterised
*real* equation system: it type checks a full `UntypedPres` on top of the same
[data specification](data-specification.md) checker, the same way
`PbesSpecification` does. `PresSpecification::from_untyped` first type checks
the embedded data specification exactly as `DataSpecification::from_untyped_with`
does, then resolves every `glob` variable's sort and every propositional
-variable equation's own parameter sorts, and finally walks every equation's
formula and `init` — resolving each `PropVarInst` by name and checking its
argument count and each argument's sort, checking each data expression
embedded via `val(...)` (and each `*`-constant multiplier) against `Real`
rather than `Bool`, and scoping `inf`/`sup`/`sum` binders to the subtree they
bind. Errors are reported as `PresError`, a superset of
`WellTypedError`/`InferenceError`.

**Scope.** As with `PbesSpecification`, this checks *sorts and names* only:
parameter/argument sort-checking, propositional-variable name/arity
resolution, binder scoping. It does **not** check PRES well-formedness
properties like monotonicity of propositional variables — a separate semantic
analysis, out of scope here.

A PRES formula shares no reparse pass with `ProcessSpecification` either, for
the same reason `PbesSpecification` doesn't: every `PresExpr` the parser
produces is already correctly shaped.

`PresSpecification::typing_info` exposes the same [span-keyed
`TypingInfo`](lsp.md) the other three specification kinds do, merged over
every checked expression (a `val(...)` expression, a `PropVarInst` argument, a
constant multiplier, a bound-variable occurrence) — computed once during the
construction walk above, so reading it back afterwards is a cheap clone
rather than a second pass.

## Extra constructs, same checking shape

A `PresExpr` has every `PbesExpr` variant's checking shape (`True`/`False`,
`PropVarInst`, `Negation`, `Binary`) plus five with no PBES counterpart, none
of which change how checking is structured — each is just another node the
scoped walk recurses through, or (for `DataValExpr`/the constant multipliers)
another leaf checked against `Real`:

- `Equal { eq, body }` (`eqinf(...)`/`eqninf(...)`) and
  `Condition { condition, lhs, then, else_ }` (`condsm(...)`/`condeq(...)`)
  both just recurse into their `PresExpr` children — none of the three
  arguments to `condsm`/`condeq` is a boolean guard, so there is nothing to
  check beyond that shared recursion.
- `{Left,Right}ConstantMultiply { constant, expr }` (`val(...) * X` /
  `X * val(...)`) checks `constant` against `Real` and recurses into `expr`.
- `Bound { op, variables, expr }` (`inf`/`sup`/`sum x: D . expr`) is
  `PbesExprKind::Quantifier`'s counterpart: `pres/check.rs`'s `collect_scope`
  resolves `variables`' declared sorts into the same flat, span-keyed `Scope`
  `checking::collect_binder_sorts` builds for a PBES's `Quantifier` or a
  process's `Sum`/`Dist`.

## Declaration tables

`PresSpecification` resolves the same single-slot `name -> (parameters, ...)`
table `PbesSpecification` does for its propositional-variable equations, one
entry per equation. A PRES equation is declared once each, exactly like a PBES
one: re-declaring an already-declared `X` is a
`PresError::DuplicatePropositionalVariable`, not an overload.
