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
