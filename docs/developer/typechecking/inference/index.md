# Inference Internals

[Sort Inference](../sort-inference.md) covers Phase 3 at the level of *what*
it computes and *why* it is correct: the sort lattice, the constraint kinds,
and the ranked search that picks the most specific typing. This subdirectory
is the implementation-level companion — *how* the two source files behind
that page actually work, walked function by function with pseudocode, for
anyone about to modify them.

Phase 3 lives in `crates/typecheck/src/inference/` as two files with a clean
split of responsibility:

- **[`unification.rs`](unification.md)** — the
  [`Unifier`](https://mercorg.github.io/merc/merc_typecheck/inference/unification/struct.Unifier.html):
  structural unification over a union-find table, an append-only arena of
  sort nodes under construction, and the subsort-lattice queries the solver
  enumerates during widening. It knows nothing about equations, constraints,
  or overloads — only "are these two sort expressions equal, and if not, what
  concretely might make them so."
- **[`inference.rs`](solver.md)** — [`ConstraintGenerator`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.ConstraintGenerator.html) and
  [`Solver`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.Solver.html): the per-equation driver that walks the AST once to
  emit [`Constraint`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html)s, then backtracks over them, calling into the
  `Unifier` at every choice point and ranking the leaves it reaches.

Both are exercised fresh per equation: [`infer`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/fn.infer.html) constructs one
[`Unifier`](https://mercorg.github.io/merc/merc_typecheck/inference/unification/struct.Unifier.html) as a local variable, runs generation and solving against it, and
drops it — arena included — before returning. Nothing in either file persists
state across equations; the only cross-equation state is the memoized
[`EquationTyping`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.EquationTyping.html) result itself, cached on
[`TypeCheckContext`](https://mercorg.github.io/merc/merc_typecheck/struct.TypeCheckContext.html).

## Reading order

1. **[The Unifier](unification.md)** — the data model (`InferSortId` vs.
   `SortVar`), the structural unification algorithm, the occurs check, the
   subsort-lattice queries, and exactly what snapshot/rollback does and does
   not undo.
2. **[Constraint Generation & the Solver](solver.md)** — how one equation
   becomes a flat constraint list, how that list is solved by ranked
   backtracking, and how the winning leaf is extracted into a typing.

Both pages assume you have already read [Sort Inference](../sort-inference.md)
for the conceptual vocabulary (the lattice, join/meet, the five constraint
kinds) — they don't re-derive it, only show how it is implemented.
