# Process Specification

`DataSpecification` only ever covers the data language. `ProcessSpecification`,
built on top of it, type checks a full `UntypedProcessSpecification`:
`ProcessSpecification::from_untyped` first type checks the embedded [data
specification](data-specification.md) exactly as
`DataSpecification::from_untyped_with` does, then resolves every `act`
argument sort and `glob`/`proc` parameter sort, and finally walks every `proc`
body and `init` — action and process-instantiation arguments against their
declared sorts (with overload resolution where a name is declared more than
once), `sum`/`dist`-bound variables in scope for the subtree they bind,
conditions against `Bool`, and time bounds/`dist` weights against `Real`.
There is no lower-level entry point that type checks a process body without
first running the reparse pass below — every path goes through
`from_untyped`. Errors are reported as `ProcessError`, a superset of
`WellTypedError`/`InferenceError`. Communication sort-compatibility is not
checked yet.

## The `.`/`+` grammar-ambiguity reparse pass

mCRL2's concrete syntax overloads tokens between the process algebra and the
data language — most notably `.` (process sequential composition vs. the data
"at"/indexing operator) and `+` (process choice vs. data addition).
Disambiguating the two readings needs semantic information a context-free
grammar doesn't have, so `merc_syntax`'s grammar always takes the greedier
data-expression reading: `act(args) . cond -> P <> Q` parses `act(args) . cond`
as a single data expression rather than an action step followed by the real
condition, and `cond1 -> P1 + cond2 -> P2` folds `cond2` into `P1`'s subtree
instead of starting a sibling clause. In both cases the misparse always lands
in the same place — a `Condition` node's `condition` field, the one `DataExpr`
slot in the process grammar with no delimiter bounding how far it extends.

Before type checking runs, `crate::process::reparse` walks the specification and
rewrites every misparsed `Condition` back into the `Sequence`/`Choice`/ `Action`
shape it should have parsed as. This needs only the declared action/process
*names*, matching how mCRL2 itself resolves the same ambiguity before its own
type checking runs. Because the pass runs unconditionally first, the
process-body walk never needs error-driven recovery of its own — every
`Condition` it sees is already correctly shaped.