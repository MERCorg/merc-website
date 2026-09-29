# Enumeration

## Bindings along a branch

The search is breadth-first, so many partially-instantiated branches are
outstanding at once, and each one extends a shared prefix of the bindings
chosen so far. Representing a branch's bindings as an owned map per work item
would copy that prefix on every expansion, so `merc_enumerate` keeps them as
a linked list of `(variable, value)` nodes in one arena owned by the
enumerator: extending a branch is a push, and every sibling that shares the
prefix stays valid. The arena is cleared, not dropped, between searches, so a
caller driving many searches through one enumerator — LPS `sum`-successor
generation is the motivating case — reuses its capacity.

A chain is deliberately *not* a general substitution. A variable's image may
mention variables bound later in the same chain (`v ↦ c(y1, y2)` where `y1`
and `y2` are fresh variables introduced to expand `v`), so splicing a chain
into a term with other free variables outstanding would leave them behind.
It is only used that way to normalise the search's own goal body, where the
enumerator knows exactly which variable is being replaced; resolving a
finished branch to ground values instead walks the chain recursively.

That resolution has to rewrite as it goes, not only at the leaves.
Substituting already-normal arguments into a constructor can still leave the
composite reducible — under the machine-word `Nat` encoding, `@succ_nat`
applied to a normalised digit still needs its carry-propagating equation to
fire — and the values handed back to a caller are spliced straight into
further rewrite calls as substitution images, which requires them to be normal
forms.

## Testing the enumerator against a second implementation

`merc_enumerate` ships a `NaiveEnumerator` alongside the real one, in the
same role [`merc_sabre::NaiveRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.NaiveRewriter.html) plays for the rewrite engines:
materialise every ground term of each variable's sort up to a size bound,
substitute all variables at once, rewrite once per combination. No
incremental normalisation, no pruning, no one-point rule, no fairness scheme
to get wrong. Random goals are then run through both and their solution
*sets* compared.

Two things make that suite cheap enough to run 200 goals per invocation.
Goals are built through the [`merc_data`](https://mercorg.github.io/merc/merc_data/index.html)/[`merc_sabre`](https://mercorg.github.io/merc/merc_sabre/index.html) API rather than
generated as source text, so neither the parser nor the typechecker runs per
goal. And the rewriters are built once, outside the loop: constructing an
[`InnermostRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.InnermostRewriter.html) compiles a [`SetAutomaton`](https://mercorg.github.io/merc/merc_sabre/struct.SetAutomaton.html) over every equation the
specification carries, which includes the whole lowered built-in library
(331 equations even for a specification declaring one small custom sort), so
rebuilding one per goal dominated the runtime of an earlier version of the
test — over a CPU-minute for 200 goals, against well under a second with the
rewriters shared. A real caller builds its rewriter once per run for exactly
the same reason.
