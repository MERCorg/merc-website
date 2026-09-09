# LSP Support

The type checking pipelines tracks sorts internally by
`ExprId`, an index assigned over the *lowered* expression tree — it can
contain nodes with no counterpart in the original, unlowered syntax a caller
parsed (the desugared `Id("+")` of `x + y`, for instance), so an external
caller such as an editor integration cannot safely reconstruct it by
re-walking the original tree after the fact.

`DataSpecification::typing_info` (whole specification) and
`DataSpecification::equation_typing_info` (one equation) instead expose a
`TypingInfo`: one `TypedNode` per checked expression node — its source `Span`,
its inferred sort (reconstructed as a `SortExpression` for display, or `None`
for a node with no data sort to report at all — see below), and what its
identifier resolved to (`ResolvedName`: a variable, a user `Constructor`/
`Mapping`/`Action`/`Process` with its declaration span when it has one, a
system-defined Appendix-B symbol, or a polymorphic builtin) — keyed by that
`Span` rather than any internal id. `TypingInfo::at_offset` answers the
hover/go-to-definition query directly: the most specific node whose span
contains a byte offset, breaking span ties (a synthesized node inherits its
surface expression's span, so e.g. `x + y`'s synthesized `Id("+")` and its
`Application` node can share one span) in favor of the later, more specific
node in generation order. `DataSpecification::typecheck_expression_with_typing`
gives the same `TypingInfo` for a single standalone expression checked outside
any specification. Note that a `TypedNode`'s reconstructed *sort*, when
present, always carries `Span::default` — a resolved sort has no reliable
source location of its own, since name resolution and alias normalization both
discard or relocate a sort's original span — so this API can't answer sort
go-to-definition from `TypedNode::sort` alone; use the `Def` sort's carried
`DefId` instead.

[Process, PBES, and PRES](../specification/index.md#span-keyed-typing-info-lsp-support)
specifications expose the same API over their
own subtrees: `ProcessSpecification::typing_info` merges every checked
process-body expression (action arguments, process-instantiation arguments,
conditions, time bounds, `dist` weights); `PbesSpecification::typing_info`
merges every checked PBES expression (`val(...)` expressions, `PropVarInst`
arguments, quantifier binders); `PresSpecification::typing_info` merges every
checked PRES expression (the same, plus constant multipliers and
`inf`/`sup`/`sum` binders). All three are computed once during their
respective `from_untyped_with` construction walk — the walk that resolves
names and sorts already visits every node, so exposing the accumulated
`TypingInfo` needs no extra pass — and `typing_info()` just clones the stored
value.

`DataSpecification::typing_info`/`equation_typing_info` take `&mut self` for
the same reason, but for a different one underneath: a `DataSpecification` is
immutable once built, so a *second* call for the same document/equation would
otherwise redo the work — rebuilding the `DeclarationIndex` and re-deriving
every node's sort — for no reason. Both are memoized on `TypeCheckContext`
(a `QueryCache` per equation, a `whole_typing_info` singleton for the whole
document, mirroring the existing `signature` field), so a second call reuses
the cached `Arc` and just clones out of it. This matters most for an LSP: a
hover request calling `typing_info()` once per keystroke would otherwise pay
for a full re-derivation on every call.

This is groundwork for LSP-style tooling (hover, go-to-definition) rather than
a consumer of it — no editor integration exists in this repository itself, but
an experimental language server built on it lives at
[MERCorg/merc-lsp](https://github.com/MERCorg/merc-lsp).

## Variable go-to-definition: a syntactic pre-pass

A variable occurrence's identity is settled by a dedicated pass that runs
*before* type checking starts, not by the checker itself.
`resolution::variable_resolution::resolve_process_variables`/
`resolve_pbes_variables`/`resolve_pres_variables`/
`resolve_data_specification_variables` each walk their untyped tree (a
`proc`/`init` body, a PBES or PRES equation/`init`, or a data specification's
own `var`-block equations, respectively) and rewrite a context-free variable
occurrence's `DataExprKind::Id(name)` into `DataExprKind::Resolved(name,
VarId)` wherever `name` names a binder currently in (lexical) scope —
`sum`/`dist`, a process's own parameters, a PBES quantifier/equation
parameter, a PRES `inf`/`sup`/`sum`/equation parameter, a lambda/quantifier/
comprehension/`whr` binder, or a data specification's own `var`-block
declaration. A name resolving to nothing in scope is left as a plain `Id`,
unresolved by this pass — the existing `UndeclaredName` inference error still
catches it later, this pass cannot fail on its own. Each binder's own
declaration (`IdDecl`) gets its `VarId` assigned here too, via a
`VarIdAllocator` — every binder site except a constructor/map declaration
carries one — so a `VarId` is the one identity a binder and every occurrence
resolving to it agree on. The pass's own `Scope(Vec<(String, VarId)>)`
(distinct from `checking::Scope` below) is a transient name→`VarId` shadowing
stack that exists only to answer "which binder does this name currently
refer to" while walking; it's discarded once the walk finishes.

The same pass also builds `VariableSpans` (`HashMap<VarId, Span>`), pairing
each binder's `VarId` with the span of the identifier it declares — this is
the table `ResolvedName::Variable`'s `declaration: Option<Span>` is later
resolved from (by `VarId`, in `typing_info::resolved_name`), not something
carried on the `Resolved` node itself. Keeping the span in a side table
rather than a third field on `Resolved` means an ordinary reference
occurrence stays a plain `(name, VarId)` pair — the declaration site is only
ever looked up by the handful of callers that build a `TypingInfo` at all,
not paid for by every sort-inference lookup along the way.

This works as a *pre*-pass, unlike constructor/mapping resolution, because a
variable reference is genuinely context-free: "which binder does this
occurrence refer to" is answerable in one syntactic walk over the untyped
AST, with no dependency on any inferred sort. And because every binder — down
to a `lambda`/`forall`/`exists`/comprehension/`whr` nested inside a single
expression — is already resolved to a `VarId` by this one walk, `gen_name`
(`inference.rs`) never needs a second, by-name fallback scope for a binder
introduced *within* the expression currently being inferred: `declared_sorts`
is the only lookup, keyed uniformly by `VarId` regardless of how local the
binder is.

Because every variable occurrence in a `proc` body/PBES or PRES equation is
already a `Resolved` node by the time `process::check`/`pbes::check`/
`pres::check` run, none of the three threads its own name-shadowing scope
stack either: `checking::Scope` is a flat `[(VarId, ResolvedSortId, Span)]`
table, collected once per `proc` body/PBES/PRES equation (`collect_binder_sorts`,
walking `Sum`/`Dist`/`Quantifier`/`Bound` binders) before any of its leaves
are checked, rather than pushed and popped as the check walk descends. Unlike
`declared_sorts` above, this table *does* carry the declaration span directly
alongside the sort — the process/PBES/PRES/modal layer sits outside
`DataSpecification`'s own equation numbering, so it has no shared
`VariableSpans` of its own to defer to and keeps its span eagerly instead.

## A standalone expression's own variable spans

`DataSpecification::typecheck_expression_with_typing` checks one closed
expression outside any specification (see its own doc comment: a free
identifier is an `InferenceError::UndeclaredName`, since there is no
enclosing `var` block to draw variables from). It ties the expression's own
local binders with `resolve_data_expr_variables` — the same pre-pass above,
but started from an empty `Scope` rather than a whole specification's or
process's — and passes the resulting local `variable_spans` straight to
`typing_info::build`. The `TypingInfo` this returns is self-contained and
safe to use as-is.

What is *not* safe is reusing that local `variable_spans` (or the `VarId`s
inside the `TypedNode`s it produced) against a *different* resolution pass's
tables — say, treating an identifier inside `expr` as if it could resolve
against a full process's own `self.variable_spans`. Two independent problems
rule this out:

- **Scope.** `resolve_data_expr_variables` starts from an empty `Scope` by
  design, so it cannot see a process's globals or parameters; a name that is
  actually process-scoped is either left an unresolved `Id` (and later
  rejected as `UndeclaredName`) or — if it happens to also name a
  constructor/mapping — silently resolves to that instead.
- **Numbering.** Every pre-pass call allocates its `VarId`s from a fresh
  `VarIdAllocator::default()`, which restarts at `0` (see [`IdAllocator`
  in `merc_utilities`](https://github.com/MERCorg/merc/blob/main/crates/utilities/src/tagged_index.rs)).
  A `VarId` is therefore only meaningful against the `VariableSpans` map the
  *same* call produced. `VarId(2)` from one call and `VarId(2)` from another
  are unrelated declarations that happen to share a number, not the same
  variable looked up twice.

## Action and process-instantiation names: resolved by the checker, not the pre-pass

`ProcessExprKind::Action`/`Id`'s `name` is the opposite case from a variable
occurrence: it is resolved by
[`check_action_or_process`/`check_instantiation`](../specification/index.md#a-second-unrelated-ambiguity-action-vs-process-instantiation) —
an overloaded, arity-and-sort-based lookup that needs an argument's *inferred*
sort to pick the right declaration, the same category `Constructor`/`Mapping`
resolution falls into. So it cannot move into the syntactic pre-pass above; it
is resolved inside the type checker itself, once a unique candidate wins.

`Action`/`Id`'s `name` field is an `ActionName` (`Spanned<String>`, the same
wrapper `Hide`/`Block`'s `actions: Vec<ActionName>` already use), carrying its
own span distinct from the whole `name(args)` node's. `ResolvedName` gained two
matching variants, `Action { name, declaration }` and
`Process { name, declaration }`. Since neither is backed by any `DataExpr` —
`typing_info::build` only ever sees the `DataExpr` half of a specification —
`TypingInfo::push` records one directly, at the name's own span, once
`check_action_or_process`/`check_instantiation` know the single winning
candidate (alongside merging that candidate's own argument `TypingInfo`, as
before). This is also why `TypedNode::sort` is `Option<SortExpression>`: an
action/process reference has no data-expression sort to report — mCRL2 gives
it a *domain*, not a value sort — so these two node kinds are `None` there,
the only case that arises today.

## Action-name sets and propositional-variable instantiations

A `hide`/`block`/`allow`/`comm`/`rename` action-name set
(`ProcessExprKind::Hide`/`Block`/`Allow`/`Comm`/`Rename`'s `actions`/`comm`/
`renames` fields) has no argument list to disambiguate an overloaded name by
the way `check_action_or_process` does, so `check_action_names` can't narrow
it down to one declaration. Rather than guess, it offers all of them:
`ResolvedName::ActionSet { name, declarations: Vec<Span> }` carries every
same-named `act` declaration's span, in declaration order — a goto-def
consumer decides what to do with more than one (jump to the first, offer a
picker, …). See
[action-name-set-goto-def-plan.md](https://github.com/MERCorg/merc/blob/main/docs/action-name-set-goto-def-plan.md)
for the design this settled on.

A PBES/PRES propositional-variable instantiation (`X(e1, e2)`, including a
bare `init X;`) resolves the opposite way: `pbes::check`/`pres::check`'s
`check_prop_var_inst` pushes `ResolvedName::PropositionalVariable { name,
declaration }` once it confirms `X` is declared. Unlike an action or process
name, this is never ambiguous — a PBES/PRES equation is declared at most once
per name (a second `mu`/`nu X = ...` is a `DuplicatePropositionalVariable`
error, not an overload) — so there's exactly one declaration to point at, the
same single-`declaration` shape `Action`/`Process` use. It's pushed at the
whole `PropVarInst`'s own span rather than just an identifier prefix (there
is no separate one to carry), which still resolves correctly everywhere it
matters: an offset over one of the instantiation's own arguments finds that
argument's own narrower typed node first (`TypingInfo::at_offset`'s
tie-break), so only an offset actually over the identifier prefix ever
reaches this node.
