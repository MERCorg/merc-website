# The STARK Library

The `merc_stark` crate implements the STARK specification language: a parser,
name resolver, type checker, lowering pass and evaluator for the language of
the *Software Tool for the Analysis of Robustness in the unKnown environment*
([STARK](https://github.com/the-stark-tool/STARK)), which is originally
implemented in Java. STARK models a system as an *evolution sequence*, a
sequence of probability measures over application-relevant data, and specifies
properties over such sequences using *Robustness Temporal Logic* (RobTL).

> Valentina Castiglioni, Michele Loreti, Simone Tini: STARK: A Software Tool for the Analysis of Robustness in the unKnown environment. COORDINATION 2023: 115-132

The grammar implemented here follows the original ANTLR grammar
(`StarkSpecificationLanguage.g4`) rather than extending it, so a specification
that the Java tool accepts is also accepted here. That implies a number of
limitations — no `//` line comments, no parenthesised RobTL formulas, no
implication operator — which are limitations of the language itself rather than
of this port. They are listed, with the workaround for each, in `plan.md` in
the crate root, which also tracks everything still open.

## The Pipeline

A specification passes through four stages before it can be run:

```text
parse -> resolve -> typecheck -> lower -> IrProgram -> evaluate
```

Each stage is a distinct type, so a later stage cannot be reached without
passing the earlier ones:

 - `UntypedStarkSpecification::parse` produces a faithful syntax tree whose
   references are still unresolved and whose expressions have no types yet.
 - `UntypedStarkSpecification::check` runs name resolution and type checking,
   and produces a `StarkSpecification` — the syntax tree paired with the
   `SymbolTable` and `TypeTable` that describe it.
 - `lower` turns a `StarkSpecification` into an `ir::IrProgram`.
 - `eval::Simulation` and `eval::Analysis` run an `IrProgram`.

Only `check` can produce a `StarkSpecification`, so anything holding one knows
that resolution and type checking already succeeded and never has to re-derive
or re-validate that. Type checking runs even when resolution reported errors —
unresolved references simply stay unresolved and the checker skips them — so a
single call reports the problems from both passes together, rather than making
the user fix every name error before seeing any type error. Errors from both
passes are collected in a `Diagnostics`, which renders them against the
original source.

## The Evaluation IR

### Why an arena rather than a closure tree

The Java implementation lowers each expression into a **closure tree**:
`StarkExpressionEvaluator` returns a `StarkExpressionEvaluationFunction`
(`(RandomGenerator, StarkStore) -> StarkValue`), and every operator captures
its operands' closures. Evaluation is therefore a chain of megamorphic virtual
calls through heap-scattered lambda objects, and every variable read goes
through a `StarkStore` — which, depending on which factory built it, is a
`HashMap` lookup, a linear `let`-chain walk, or an array index.

This port lowers to a **flat arena of IR nodes** instead:

 - Subexpressions are referenced by `ExprRef`, an index into one
   `Vec<ExprNode>`, rather than by `Box` or closure. Nodes are small, `Copy`
   and contiguous, so evaluation walks an array instead of chasing pointers.
 - Every name that resolution bound — global variables, constants, parameters,
   function arguments, `let` bindings — is assigned a `SlotId` **at lowering
   time** and stored directly in the node. A variable read is `store[slot]`, a
   single indexed load: no maps, no name strings, no scope chains at runtime.

That is the whole point of the pass. All the work `resolve.rs` already did gets
baked into the node so that the evaluator never re-derives it.

Expressions, statements and commands each live in their own arena and are
referred to by index types (`ExprRef`, `StmtRef`, `CommandRef`, `SlotId`, …)
that are all backed by a `u32` but carry a distinct tag, so an `ExprRef` can
never be mixed up with a `SlotId` at a call site. The same reasoning applies one
level up: `PerturbationIr`, `DistanceIr` and `FormulaIr` are each their own
flat, `Box`-free arena, since their operands are themselves recursive
sub-expressions and lowering them as trees would have reintroduced exactly the
heap-scattered shape this port exists to escape.

### One flat slot space works because STARK has no recursion

`resolve.rs` enforces no forward references, including for functions: a
function's `DefId` is registered only after its own body resolves, so
self-recursion is a resolve-time error, and mutual recursion is impossible for
the same reason. **No function can therefore ever be live on the stack twice**,
and every local binding in the program can be given its own distinct,
statically allocated slot. There is no need for call frames, frame pointers, or
any push/pop at all: a call writes its arguments into the callee's fixed slots
and evaluates the body.

This is a consequence of the language's design rather than an assumption, and
it is asserted rather than trusted — `lower_call` checks
`callee_id < current_function_id`, and `bind_local_slot`/`bind_def_slot` reject
a second slot allocation for a binding that already has one.

The same property is what lets the `Reference` cases of
`PerturbationExpression`, `DistanceExpression` and `RobtlFormula` be resolved to
the referent's *root* id at lowering time. A reference can only ever name
something already lowered, so no name lookup survives into the IR anywhere.

### Slot layout

One flat `Vec<Value>` store, partitioned so that the interesting range is
contiguous:

| Range | Contents | Mutability |
|---|---|---|
| `[0, n_variables)` | system variables (the simulation state) | read/write each step |
| `[n_variables, n_globals)` | `const` and `param` values | written once at startup |
| `[n_globals, n_slots)` | function arguments and `let` bindings | scratch |

Variables come first so that the state vector the evaluator checkpoints,
perturbs and compares is a plain contiguous prefix slice, with no gather or
scatter. `IrProgram::validate` re-checks this partition — that each slot's
`SlotKind` matches its index range, and that every `VariableInfo::slot` lies in
the prefix — because `n_variables()` and `n_globals()` derive the boundaries
from list lengths rather than by scanning, and the evaluator slices on that
basis.

**Constants and parameters get slots rather than being folded in.** Java
eagerly evaluates them to a `StarkValue` at generation time and substitutes the
value. Giving them slots instead means the IR carries an ordered
`Vec<GlobalInit { slot, value: ExprRef }>` that the runtime executes once at
startup. That costs nothing at steady state and makes `param` genuinely tunable
without re-lowering, which is what `param` is *for* in an experiment harness. It
also means lowering needs no constant evaluator at all, keeping all evaluation
in the evaluator. Interval bounds (`\F[from,to]`, `@time`, `^iterations`) stay
`ExprRef`s for the same reason.

### Semantics that are easy to get silently wrong

**Assignments are buffered, not applied immediately.** `CommandNode::Assign`
holds an `Update { target, guard, value }`, and updates are collected into a
list that is applied at the end of the step, so every read within a step sees
the *pre*-state. This preserves Java's `DataStateUpdate` / `ds.apply(...)`
semantics exactly. Getting it wrong would silently change the meaning of every
multi-assignment environment block, so it is pinned by tests using the classic
`x' = y; y' = x;` swap.

**Lowering does not enforce that every path through a controller state reaches
a `step` or `exec`.** A `Sequence(a, b)` where `a` contains a transition simply
leaves `b` unreachable at evaluation time. Whether that is an error is an
evaluator concern; lowering only preserves the source structure faithfully.

**`exec target` is a reference to the target state, not a copy of its body.**
Every `state`/`exec` target is pre-allocated an `IrStateId` and a placeholder
`StateIr` before any body in the component is lowered, so forward and backward
references both resolve — mirroring `resolve.rs`'s own two-pass treatment.

### Errors, assertions and debug information

`lower` takes a `StarkSpecification`, which by construction can only exist if
resolution *and* type checking succeeded, so lowering may treat every
`DefRef::id`, `Binding` and `StateRef::id` as `Some` and every `DefId` as typed.
Anything violating that is a bug in an earlier pass rather than user error, and
is **asserted rather than diagnosed**. Those assertions degrade gracefully in
release builds, skipping the declaration instead of aborting, so a
`debug_assert` never becomes a production panic.

`lower`'s `Result` exists for exactly one error class: constructs that check but
have no IR representation yet, reported as
`DiagnosticKind::NotYetSupported`. Nothing in the current grammar reaches that
path — Java has the same hole, with `visitControllerCaseStatment` left as a
`//TODO: FIXME!` — but the seam is kept for the next construct that needs it.

`IrProgram::validate` independently re-checks the finished arena: in-bounds refs
of every id kind, list slices within `expr_lists`, the slot partition, and
parallel-array lengths. It runs under `debug_assert!` at the end of `lower` and
directly in tests. That is the cheap way to keep an arena IR honest, since arena
corruption is otherwise diagnosed only as a nonsense result far downstream.

Debug information is two things, both present. **Source spans survive into the
IR** — `expr_spans` runs parallel to `exprs`, and `SlotInfo` carries a span, so
nodes stay small and cache-dense while remaining attributable to source. And
**`log` tracing is consistent across `resolve`, `typecheck` and `lower`**:
`debug!` once per pass with a summary, `trace!` per declaration lowered and slot
allocated. Tests use `test-log`, so `RUST_LOG=merc_stark=trace cargo test` shows
the whole pipeline. `IrProgram` also has a hand-written `Display` that prints
the arena back as resolved, indented, source-like text, because raw `Debug` on
an arena (`Binary(Add, ExprRef(3), ExprRef(7))`) is unreadable; `Display` is
what the snapshot tests assert on.

## The Evaluator

There are two entry points, one per thing that can be asked of a specification.

**`eval::Simulation` runs it.** It owns the store and each component's
controller cursor, and steps the whole system one macro-step at a time. It is
deliberately push-based: `Simulation::run` takes an `Observer` and calls it
after every step rather than eagerly building a trajectory. A caller can
therefore stop early or aggregate on the fly, and an ensemble driver can be
built on top without `Simulation` itself changing. For callers that do want the
whole trajectory materialised, `RecordingObserver` collects it.

```rust
use merc_stark::UntypedStarkSpecification;
use merc_stark::eval::{RecordingObserver, Simulation};
use merc_stark::lower;

let specification = UntypedStarkSpecification::parse(source)?.check()?;
let program = lower(&specification)?;

let mut simulation = Simulation::new(&program, 42)?;
let mut observer = RecordingObserver::default();
simulation.run(50, &mut observer)?;
```

**`eval::Analysis` verifies it.** It samples an ensemble — an
`eval::EvolutionSequence`, a sequence of sample sets approximating the
distribution over states at each time step — perturbs a copy of it, and
evaluates the specification's `distance` and `formula` declarations. Both
semantics from the reference are available: the three-valued one (`check`,
returning an `eval::TruthValue`, backed by the bootstrap confidence interval
`eval::Ci`) and the boolean one (`check_boolean`).

Internally, a perturbation is a coroutine rather than an object graph.
`PerturbationState` keeps only what changes over time — the countdowns — while
the static part of an atomic perturbation stays in the `PerturbationIr` arena
and is referenced by id. Two of Java's six cases, `AfterPerturbation` and
`PersistentPerturbation`, have no counterpart because the grammar cannot
produce them.

A simulation is seeded from a `u64`, and the same seed reproduces the same
trajectory. That stream is **not** bit-compatible with the Java reference, which
uses a Mersenne Twister; only the sampled *distributions* match.

### Errors are a `Result`, not a value

The Java reference propagates failure as an absorbing `StarkValue.ERROR_VALUE`
that contaminates every operation it touches. Every entry point here returns
`Result<_, EvalError>` instead, so a failure stops evaluation at its source
rather than silently producing a value that happens to be an error.

`EvalError` is a `{ kind: EvalErrorKind, span: Option<Span> }` pair, the runtime
counterpart of `Diagnostic`/`DiagnosticKind`. The *class* of failure lives in
`EvalErrorKind`, and `eval::expr::eval` anchors it to the offending
expression's `Span` as the error unwinds. The innermost expression wins, via
`EvalError::or_span`, so `1 / 0` nested in `4 + 1 / 0` is reported against the
division rather than the whole initializer, and `EvalError::render` prints it in
the same `-->`/`^^^` style as the compile-time diagnostics.

`Value`-level operations yield a bare `EvalErrorKind`, since they have no span
to give, and are lifted by `From`. The sample-shape errors
(`IncompatibleSampleSizes`, `EmptySampleSet`) and the variants that are
unreachable against a checked program keep `span: None`, because they are not
tied to any one source expression.

## Status

Parsing, name resolution, type checking and lowering are complete for every
construct the grammar accepts, and are tested against every example
specification under `examples/stark/`. Simulation of a single trajectory and
robustness analysis of `perturbation`, `distance` and `formula` declarations —
under both the three-valued and boolean semantics — are implemented and tested
end to end.

What remains is tracked in `plan.md` in the crate root: the known divergences
from the reference, the parts of the Java runtime that have no textual syntax
at all (compositional penalties, feedback, the DisTL online-monitoring
formalism, timed systems, the Skorokhod distance), and the tooling gaps against
the Java interactive shell.
