# Overview

`merc_linearisation` turns a type-checked `merc_typecheck::ProcessSpecification`
into a `LinearProcessSpecification` (LPS): a flat vector of process parameters
plus a set of `sum d:D . c(d,p) -> a(f(d,p)) . P(g(d,p))`-shaped summands — the
condition/action/effect form the rest of merc (`merc_lts`, `merc_explore`,
`merc_symbolic`) is built around. It is a native, from-scratch port of the
algorithm mCRL2's `libraries/lps` (`source/linearise.cpp`, ~10k lines)
implements. The full phased design — including the milestones not built yet —
lives in [`docs/linearisation-implementation-plan.md`](https://github.com/MERCorg/merc/blob/main/docs/linearisation-implementation-plan.md)
in the merc repository; this page is about the design choices behind what
*is* built — Milestone 1 (a single, self-recursive, `||`-free process),
Milestone 2 (compositional linearisation for `tools/lts combine`), and an
alphabet-based simplification pass added on top of both — and why they turned
out the way they did, several only after the corpus of real `.mcrl2` examples
merc vendors (`examples/mCRL2/`) pushed back on the first attempt.

## Why the data model stays at the `merc_syntax` level

The obvious choice would be to lower every condition/action-argument/
next-state expression into `merc_data`'s aterm representation, the way
`DataSpecification::lower_data_specification` already does for data
equations — it's what the rest of merc (the rewriter, the LTS explorer)
eventually needs. Milestone 1 doesn't do this, for a mundane reason:
`ProcessSpecification` doesn't expose a way to. It type checks a process
body's expressions and records their sorts in a span-keyed `TypingInfo` side
table, but the expressions themselves stay as `merc_syntax` syntax trees —
there's no `lower_process_specification` alongside
`lower_data_specification`. Building one is real work (the process-body
scope includes `sum`/`glob`/`proc`-parameter variables `lower_data_specification`
never has to deal with) and belongs to `merc_typecheck`, not to a translator
that just rearranges the expressions it's handed. So `LinearProcessSpecification`
holds `merc_syntax::DataExpr`, and `merc_linearisation::print` renders it back
to mCRL2 concrete syntax — good enough to feed to the FFI-backed real mCRL2
library (`tools/mcrl2`) as an interchange format, until that lowering exists
and a native rewriter/enumerator makes a direct `merc_explore::LPS` adapter
worthwhile.

## The translation is a structural fold, not a special case per operator

Reading `linearise.cpp` first suggests the algorithm is a large pile of
special cases — allow, block, hide, rename, communication all get their own
900-line header. In the fragment Milestone 1 covers (no `||`, so no
communication combinatorics at all), it collapses to one idea: every process
expression denotes a *set of summands*, and every operator is a fold over
that set.

- `Choice` — set union.
- `Sequence` — for each summand on the left that could still do *more*
  afterwards, splice the right operand's summands onto its tail; a summand
  that already reached `delta` absorbs nothing (`delta . Q` is `delta`,
  never `Q`).
- `Sum` — prepend the bound variables to every summand's own binder list.
- `Condition` — conjoin the guard into the `then` branch, its negation into
  the `else` branch (or a synthetic `delta` branch when there is no
  `else`), then union the two summand sets.
- `Rename`/`Hide`/`Block` — a per-summand rewrite of the already-collected
  multi-action (substitute a name; drop a name; drop the whole summand if it
  performs a blocked name) — no recursion into "how was this summand built"
  needed at all.

This is why the translator's core (`translate.rs`) is one recursive function
matching on `ProcessExprKind`, each arm a few lines, rather than the kind of
special-purpose machinery `linearise_communication.h` needs once `||` is in
scope (Milestone 3).

### Telling `delta`, "fell off the end", and "recurses" apart

The one piece of state that isn't just "the summand so far" is what a summand
does *next*. Three cases look interchangeable in isolation — `delta`,
`tau . nil`, and a bare recursive call `P(e)` — but `Sequence` has to treat
them differently: `delta . Q` never reaches `Q`, `(a . nil) . Q` does, and
`P(e) . Q` is a process call with something sequenced *after* it — not
tail-recursion, and Milestone 1 rejects it outright (`NotInTailPosition`,
mirroring mCRL2's own "regular" restriction). The translator tracks this
explicitly as a small `Tail` enum (`Deadlock` / `Terminate` / `Recurse`)
carried on every summand under construction, collapsed away once a summand is
finished — a finished summand's next-state vector is either the recursive
call's arguments, or (for `Deadlock`/`Terminate`) the parameters unchanged,
since a summand that never moves again can't be told apart from one that
just happens to revisit its current values.

## A corpus-surfaced correctness bug: `P()` is not "wrong arity"

The crate's regression net for this milestone isn't a handful of hand-picked
snippets — it's every `.mcrl2` file in `examples/mCRL2/` (the same 167-file
corpus `merc_typecheck`'s own `example_tests.rs` type checks), asserting only
that `linearise` never panics. Most of the corpus is full protocols built
from `||`, so most cases correctly return `UnsupportedConstruct` or
`MutualRecursionUnsupported` for now — that's expected, and tracked as the
work later milestones do. But one failure the first version of the translator
produced, on `examples/mCRL2/language/numbers.mcrl2`, wasn't a scope
limitation: it rejected `P()` — a call to an 8-parameter process with *no*
assignments at all — as `MissingParameterAssignment`.

That's wrong. mCRL2's assignment notation (`P(x = e, ...)`) documents that an
*omitted* parameter keeps its current value — `P()` is legal shorthand for
"every parameter unchanged," used precisely so large-parameter processes
don't have to restate everything on every self-call. The fix replaced the
error with the documented default (an omitted parameter's next-state
expression is just a reference to the parameter itself) and deleted the
error variant — there was no longer a real condition left for it to report.
This is the kind of bug a curated set of hand-written test cases is unlikely
to catch (why would a test author write a call that omits an argument on
purpose?) but a large real-world corpus finds immediately, in the first file
that happens to use the feature. As of this fix, the corpus splits as:

| Outcome | Count | Why |
|---|---:|---|
| Linearises successfully | 50 / 167 | Single self-recursive process, no `\|\|` |
| `MutualRecursionUnsupported` | 12 / 167 | Two or more mutually-calling `proc`s |
| `UnsupportedConstruct` | 105 / 167 | `\|\|`/`comm`/`at`/`dist`, mostly (`allow` is supported now — see below) |
| Panics | 0 / 167 | — |

The zero-panics row is the point of running the whole corpus rather than a
sample: a recursive-descent translator has plenty of places an `.expect()` or
an index could go wrong on an input shape nobody thought to hand-write, and
this is the test that would catch it.

## Why the compositional mode doesn't need to "cleave" anything

mCRL2 also ships `lpscleave`, which splits an *already-linearised* single LPS
back into two based on a heuristic partition of its parameters — a different
technique for a different problem (distributed state-space generation from
one flattened LPS with no source-level parallel structure left to exploit).
`merc_linearisation`'s compositional mode (`compositional::linearise_compositional`,
Milestone 2) is not that. `crates/explore::combine_lts` (used by `tools/lts
combine`) already computes `hide(H, allow(A, comm(C, L1 || ... || Ln)))` at
the LTS level, given one already-built LTS per component plus the H/A/C sets
as plain `merc_syntax` values. So when `init` is literally
`hide(H, allow(A, comm(C, P1(...) || ... || Pn(...))))`, there is nothing to
reconstruct: each `Pi` already *is* its own independent process, linearisable
by exactly the Milestone 1 core described above, with no parallel composition
inside it to expand. Milestone 2 is a thin recognizer for that top-level
shape (peeling `hide`/`allow`/`comm` in that fixed order, then flattening the
`||` chain underneath) plus a manifest tying the per-component LPS files to
the H/A/C sets, in the exact text form `tools/lts combine` already parses —
reuse, not new machinery. It doesn't even need its own "is this operand
parallel-free" check: a `Pi` that isn't gets rejected with the same
`UnsupportedConstruct` the shared per-process core (`translate::translate`)
already produces outside a compositional context, since that's the literal
same function call. Full monolithic linearisation (expanding `||`/`comm`
*anywhere*, mCRL2's actual hardest ~half of `linearise.cpp`) stays a separate,
later milestone precisely because it's a strictly harder problem than the
compositional case.

## Alphabet-based simplification, and the blow-up it caused before it was capped

The book (Groote & Mousavi §4) and mCRL2's `process::alphabet_operations`
give a standard set of axioms for eliminating a `hide`/`block`/`allow`/
`rename`/`comm` wrapper that provably has no effect on its operand — e.g.
`hide(I, P) = P` whenever none of `I`'s names occur in `P`'s *alphabet* (the
set of multi-actions, as name-multisets, `P` can ever perform). `alphabet.rs`
ports this as an unconditional pre-pass (`alphabet::simplify`) ahead of
`translate::translate`: mCRL2 gates the equivalent behind
`t_lin_options::apply_alphabet_axioms`, but since the pass only ever *removes*
a redundant node, there's no reason not to run it always.

The interesting design constraint is computing the alphabet cheaply enough.
`alphabet(P || Q)` needs interleaving *and* combination:
`alphabet(P) ∪ alphabet(Q) ∪ {merge(a,b) | a ∈ alphabet(P), b ∈ alphabet(Q)}`
— a cross product, multiplying set sizes at *every* `||` in a chain. The
first version of this module computed that exactly, and it hung
`example_tests.rs` (the whole-corpus regression test described above)
indefinitely — not on some contrived adversarial input, but on ordinary
real-world specifications with wide parallel compositions (dining-philosopher-style
N-way process networks, industrial protocols with dozens of components).
Two things make this worse than it might sound: first, `simplify` runs
*before* `translate` gets a chance to reject a `||` it doesn't support, so
even a specification Milestone 1 will ultimately refuse still pays for
computing its alphabet on the way there; second, the blow-up compounds across
a chain — each additional parallel component multiplies the running set size
again, so it's exponential in the *number* of components, not their
individual size.

The fix is the standard one for this shape of problem: give the alphabet
lattice an explicit top element. `Alphabet` is `Finite(HashSet<MultiActionName>)`
or `Unknown` ("could be any multiset of action names"). Every axiom check is
written to conservatively fail against `Unknown` (never prove a no-op that
isn't one), so bailing out to it is still sound by the same argument the rest
of the module leans on: an over-approximation can only cause a *missed*
simplification, never an incorrect one. `Unknown` is also contagious and
cheap — once one level of a wide `||` chain degrades to it, every level above
stays `O(1)` — so bounding one pairwise combination bounds the *total* cost
across an arbitrarily long chain.

The first fix that actually shipped checked the two operands' sizes *before*
multiplying them — above `MAX_PARALLEL_ALPHABET` (4096) computed entries,
give up without computing the product at all. That's correct, but needlessly
pessimistic: a size check on the *inputs* can't see that many merged pairs
are about to collide. Once several `||`s are nested, `merge(a, b)` frequently
produces the same multiset from several different `(a, b)` pairs (multiset
union is commutative, and real specifications repeat the same handful of
synchronising actions across many components), so the *true*, deduplicated
alphabet is often far smaller than `|alphabet(P)| × |alphabet(Q)|` suggests —
exactly the compositions this analysis matters most for were the ones most
likely to get an unnecessary `Unknown`.

`Alphabet::combined_with_limit` fixes this by moving the bound onto the
*output* instead of the input: `self`'s elements, then `other`'s, then every
pairwise merge are chained into one lazy iterator — nothing eagerly
collected — and drained one item at a time into a `HashSet` by
`collect_bounded`, which bails to `Unknown` the moment the *accumulated,
deduplicated* result would exceed the limit, not before. Two things fall out
of doing it this way: a composition whose true alphabet is small stays exact
however many raw candidate pairs it takes to discover that (duplicates cost
one more `HashSet::insert`, nothing else), and a composition that genuinely
explodes stops pulling further pairs the instant the limit is crossed, rather
than only discovering the problem after building the full cross product.
Because it's a lazy iterator rather than a pair of nested loops materialising
a `Vec` first, "stop early" and "stay cheap when small" both fall out of the
same code path instead of needing separate handling.

Getting the *bound-respecting* rewrite right without silently breaking the
*exact* answer needed its own check: `alphabet.rs`'s own `#[cfg(test)] mod
tests` runs `combined_with_limit` twice on the same inputs — once with the
production limit, once with `usize::MAX` — and compares the unbounded call
against a deliberately naive, nested-loop-with-no-early-exit reference
implementation of the same cross product. The naive version is obviously
correct by inspection (there is nothing to get subtly wrong about two nested
`for` loops), which is the point: it exists purely so the clever, lazy,
early-exiting version has something trustworthy to be checked against, not
because it's ever meant to run outside a test.
`tests/alphabet_test.rs`'s `test_alphabet_of_a_wide_parallel_composition_stays_bounded`
constructs a 40-way parallel composition (2^40 multi-actions if computed
exactly) as the corresponding black-box regression test.

`Comm`'s own contribution to the alphabet (`Alphabet::with_communications`)
took a different path to the same "port mCRL2, don't invent something new"
principle. The first version was a hand-rolled, single-round approximation:
for every multi-action already in the alphabet, try each communication
expression once. It's sound (another over-approximation) but not what mCRL2
actually computes, and diverges from it in an observable way — mCRL2's real
`alphabet_operations::apply_comm` keeps consuming a communication
expression's left-hand side from the *same* multi-action for as long as it
keeps matching (so `a|a|b|b` under `comm(a|b -> c)` yields `c|c`, not merely
`a|b|c`), and applies every expression in `comm` *in order*, so a later
expression can fire on a multi-action an earlier one just produced — no
separate fixed-point loop needed, one left-to-right pass over the
(statically fixed, finite) list of expressions already is one. `apply_comm`
now ports that algorithm directly rather than approximating it, so — unlike
`combined`, which is a genuine over-approximation by necessity — this part of
`alphabet.rs` computes exactly what mCRL2 would. The only remaining sense in
which it approximates the real per-summand `comm` operator is scope, not
precision: it runs over the whole static alphabet, not over which concrete
summand produced which multi-action.

One consequence worth calling out: this pass makes `comm(C, P)` linearisable
in a case `translate::translate` alone cannot — when `C` can be proven to
never actually fire against `P`'s alphabet, `simplify` drops the wrapper
entirely and `P`'s own summands are all that's left. `Comm` on its own is
still rejected as `UnsupportedConstruct`; it's specifically the *provably
inert* case that becomes accepted, as a natural side effect of an axiom that
was never about implementing `comm`, only about recognising when it does
nothing.

## A design principle carried forward to Milestone 3

Milestone 3's binary parallel composition (not built yet) has to solve a
larger-scale version of exactly the problem `Alphabet::combined_with_limit`
just solved: given `P`'s and `Q`'s already-computed summand sets, most
`(summand_p, summand_q)` pairs are dead — blocked, not matching any `comm`
expression, filtered by `allow` — and a summand (condition, effect,
bound-variable substitutions and all) is far more expensive to build than a
`MultiActionName` is to compare. The implementation plan writes down the
consequence explicitly, ahead of writing the code: pair the two summand sets
as a lazy iterator chain that checks the cheap multi-action-name key first
and only constructs the expensive merged summand for a pair that survives —
build-first-then-`retain` is the wrong shape for the same reason a
size-product pre-check was the wrong shape for `combined`, and for the same
reason: it pays for work a cheap check upfront would have avoided entirely.
