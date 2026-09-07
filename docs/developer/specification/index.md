# Specification Type Checking

`DataSpecification` only ever covers the data language. Three specification
kinds build on top of it: `ProcessSpecification` (a process algebra term),
`PbesSpecification` (a parameterised boolean equation system), and
`PresSpecification` (a parameterised *real* equation system). All three
follow the same two-step shape: `from_untyped` first type checks the
embedded [data specification](../typechecking/data-specification.md) exactly
as `DataSpecification::from_untyped_with` does, then **collects
declarations** into a lookup table before checking anything that refers to
them, and finally **type checks every expression** by walking the
specification's bodies/equations and resolving each name and sort against
those tables. Errors are reported as `ProcessError`/`PbesError`/`PresError`,
each a superset of `WellTypedError`/`InferenceError`.

## Collecting declarations

Before any body or equation is walked, each checker builds a declaration
table so that later name resolution is a lookup rather than a search:

- **`ProcessSpecification`** builds two tables, `actions_by_name` and
  `processes_by_name`, each mapping a name to a *list* of indices — mCRL2
  allows multiple `act`/`proc` declarations to share a name, distinguished by
  argument sort or arity (mirroring `abp.mcrl2`'s `s3,r3,c3: D # Bool;
  s3,r3,c3: Error;` and `abp_bw.mcrl2`'s `S`, `S(b:Bit)`, `S(d:D,b:Bit)`), so
  the table has to support overload resolution rather than a single slot per
  name. `DeclarationTables::build` rejects a specification that declares the
  same name as both an action and a process outright
  (`ProcessError::ActionAndProcessConflict`) — such a name would make every
  use later permanently ambiguous between the two tables, with no way for an
  argument-sort check to break the tie. This means that by the time checking
  runs, at most one of `actions_by_name`/`processes_by_name` ever has an
  entry for a given name; the two tables are mutually exclusive by
  construction, not by anything the check walk does itself.
- **`PbesSpecification`** and **`PresSpecification`** each resolve a single
  -slot `name -> (parameters, ...)` table for their propositional-variable
  equations, one entry per equation. A `mu`/`nu X(...) = ...` re-declaring an
  already-declared `X` is a `PbesError`/`PresError::DuplicatePropositionalVariable`,
  not an overload — a `PropVarInst` either resolves to the one declared
  equation or doesn't resolve at all, so there is no
  `NoMatchingOverload`/`AmbiguousActionOrProcess` equivalent to report for
  these two kinds.

## Type checking all expressions

Once the declaration tables exist, each checker walks every body/equation and
checks every expression it contains against an expected sort, resolving
overloaded names along the way:

- **`ProcessSpecification`** walks every `proc` body and `init`: action and
  process-instantiation arguments against their declared sorts (with overload
  resolution where a name is declared more than once — see [action vs.
  process instantiation](#a-second-unrelated-ambiguity-action-vs-process-instantiation)
  below), `sum`/`dist`-bound variables in scope for the subtree they bind,
  conditions against `Bool`, and time bounds/`dist` weights against `Real`.
  Communication sort-compatibility is not checked yet.
- **`PbesSpecification`** walks every equation's formula and `init`:
  resolving each `PropVarInst` by name and checking its argument count and
  each argument's sort, checking `val(...)` expressions against `Bool`, and
  scoping quantifier (`forall`/`exists`) binders to the subtree they bind.
- **`PresSpecification`** walks the same shape as `PbesSpecification`, but
  checks each data expression embedded via `val(...)` (and each
  `*`-constant multiplier) against `Real` rather than `Bool`, and scopes
  `inf`/`sup`/`sum` binders instead of quantifiers — see [extra
  constructs](#extra-constructs-same-checking-shape) below.

Each of the three checks *sorts and names* only. PBES/PRES well-formedness
properties like monotonicity or alternation depth of propositional variables
are a separate semantic analysis, out of scope for type checking.

## Process Specification

### Disambiguation pass

See [Grammar-Ambiguity Disambiguation Pass](../parsing/disambiguation.md) for
the full mechanism.

### A second, unrelated ambiguity: action vs. process instantiation

`name(args)` is ambiguous in a completely different way from the swallow
above, and `disambiguate` does not — and cannot — resolve it. mCRL2's grammar
uses one production, `Action`, for *both* an action instance and a positional
process instantiation; the parser hands out `ProcessExprKind::Action` for
either without knowing (or caring) which:

```rust
Rule::Action => {
    let action = Mcrl2Parser::Action(Node::new(primary))?;

    Ok(ProcessExprKind::Action(action.id, action.args).spanned(span))
}
```

`disambiguate` only ever asks "is this name declared as *either* an action or
a process" (see its `Names` set) to recognize process content while
un-swallowing a `Condition` — it never needs to know, and never determines,
*which* of the two `name` refers to. So every `Action(name, args)` node,
disambiguated or not, still carries this ambiguity into type checking, where
it is resolved as described in [Collecting declarations](#collecting-declarations)
and [Type checking all expressions](#type-checking-all-expressions) above:
`check_action_or_process` (in `crate::process::process_specification` and
`crate::process::check`) collects every arity-matching candidate across
whichever single table actually declares `name` (a no-op chain on the side
with no entry), type checks each candidate's arguments against its own
declared domain, and requires *exactly one* to succeed — zero is an
undeclared name, more than one is a genuine ambiguity the declarations
themselves didn't rule out (e.g. `act c: Nat; act c: Int;` called as `c(1)`:
`Nat <= Int` widens either way, so a bare `Nat` argument doesn't
disambiguate). Resolving an overload needs the argument expressions' *sorts*,
which only exist once type checking is underway — no amount of syntactic
reparsing beforehand could move this check earlier.

The single winning candidate identified this way is also where `name`'s own
go-to-definition span is filled in — see [LSP support](../typechecking/lsp.md#action-and-process-instantiation-names-resolved-by-the-checker-not-the-pre-pass).

## PBES Specification

Unlike `ProcessSpecification`, there is no grammar-ambiguity disambiguation
pass: a PBES formula shares no tokens between two different readings the way
a process body's `Condition` does, so every `PbesExpr` the parser produces is
already correctly shaped.

## PRES Specification

A PRES formula shares no disambiguation pass with `ProcessSpecification`
either, for the same reason `PbesSpecification` doesn't.

### Extra constructs, same checking shape

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

## Span-keyed typing info (LSP support)

`ProcessSpecification::typing_info`, `PbesSpecification::typing_info`, and
`PresSpecification::typing_info` each expose the same span-keyed
[`TypingInfo`](../typechecking/lsp.md) `DataSpecification` does, merged over
every expression the walk above checks:

- **Process** — action arguments, process-instantiation arguments,
  conditions, time bounds, `dist` weights.
- **PBES** — `val(...)` expressions, `PropVarInst` arguments, quantifier
  binders.
- **PRES** — the same as PBES, plus constant multipliers and
  `inf`/`sup`/`sum` binders.

All three are computed once during their respective `from_untyped_with`
construction walk — the walk that resolves names and sorts already visits
every node, so exposing the accumulated `TypingInfo` needs no extra pass —
so reading it back afterwards is a cheap clone rather than a second pass.
