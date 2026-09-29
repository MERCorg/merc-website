```math_preamble

\usepackage[paperwidth=40cm,paperheight=25cm,margin=5mm]{geometry}
\usepackage{algpseudocode}
% Default \Comment right-justifies with \hfill, which — combined with a wide
% page to fit long comments — leaves a huge blank gap between code and
% comment, and dvisvgm's tightpage crop then bakes that gap into the SVG:
% CSS stretches the whole (mostly blank) image to the page width, shrinking
% the actual pseudocode. Keep comments inline instead. See README.md.
\algrenewcommand{\algorithmiccomment}[1]{$\triangleright$ #1}
\newcommand{\Sat}{\mathrm{Sat}}
\newcommand{\Top}{\mathrm{top}}
\newcommand{\Bot}{\mathrm{bot}}
```
# Saturation

The `Saturation` strategy of `merc-sym` and `merc-lps` computes the reachable
states of a symbolic transition system with the algorithm of:

> Gianfranco Ciardo, Robert Marmorstein, Radu Siminiceanu, *The saturation
> algorithm for symbolic state-space exploration*, STTT 8(1), 2006.

This page explains saturation in detail, and changes compared to the paper.

## Overview

Saturation is a different *recursion*. It fixes one diagram node at a time: a
node at position $p$ is first brought to a fixed point under every event that
only touches positions $p$ and below, and only then used as a child of a node
one position higher. So a node is built once, in its final form. The
breadth-first frontiers, which are much larger than the final diagram for
asynchronous models, never exist. What it buys is therefore mostly *peak
memory*, and only indirectly time. On the pregenerated `anderson.4` fixture,
`Saturation` peaks at about 13.5k nodes in the manager against about 134k for
`BreadthFirst`.

## Setting

**State vectors and positions.** A state is a vector of $K$ values, one per
process parameter. A set of states is an LDD in which position $p$ is the $p$-th
node on every path. merc numbers positions $0, \dots, K-1$ from the *top*, the
paper numbers levels $K, \dots, 1$, so the paper's top level is the *smallest*
position here. Basically depth vs height of the tree.

**Events.** One transition group is one event $e$. It is stored as a relation LDD
over the group's *read and write* positions only, plus a `meta` LDD that says which
positions of the relation are read, written, or both. Two numbers are derived from
that:

```math
$$
\Top(e) = \min(R_e \cup W_e), \qquad \Bot(e) = \max(R_e \cup W_e)
$$
```

Outside $\Top(e)..\Bot(e)$ the event is the identity, which is the locality that
saturation exploits. A group that neither reads nor writes anything has no
$\Top$ and is dropped.

!!! note "There is no Kronecker structure here"
    The paper assumes that an event factorises into independent per-level matrices,
    $N_e = N_{K,e} \times \dots \times N_{1,e}$. mCRL2 summands do not: one summand
    can correlate parameters (`x' = y + 1, y' = x`). merc keeps a group as a single
    relation LDD, so "the successors of local value $i$" is a walk over a relation
    node rather than an array lookup. Nothing else in the algorithm depends on the
    factorisation, so the recursion is unchanged.

## Quasi-reducedness

Everything above relies on one property of oxidd's LDDs: they are
*quasi-reduced*. There is no level skipping, and no way to represent it — every
vector position has its own node on every path, `apply_relational_product`'s
meta-`0` case destructures the set as an inner node unconditionally, and there
is no "reduce" step that could elide one (`LDDRules::reduce` is
`unimplemented!()`; building a node is a raw `get_or_insert`).

The consequence is what the paper's algorithm needs: a value absent from a
node's spine means *not in the set*, never *don't care*. So growing a
position's local domain at runtime, which merc does as new values are
interned, cannot retroactively change what an existing node means — it is
safe at the diagram level. Everything that can go wrong from a relation or a
domain growing while an exploration is running is therefore in the *operation
cache*, not in the nodes; see [Caching](#caching-and-the-saturation-cache).

A second consequence: a node's height determines $p$ (position $=$ vector
length minus height), so `saturate` passes $p$ down as an argument instead of
recomputing it, and does not put it in the cache key.

## The recursion

Let $E_p = \{e \mid \Top(e) = p\}$ and let $\Sat_p(X)$ be the smallest superset of
$X$ that is closed under every event with $\Top(e) \ge p$. Then

```math
$$
\text{reachable}(I) = \Sat_0(I)
$$
```

so reachability is *one* call `saturate(initial_states, 0)`, and it works unchanged
for a set of initial states. The paper's `Generate` procedure disappears.

```math
\begin{algorithmic}[1]
\Function{Saturate}{$q, p$}
  \If{$q$ is a terminal} \State \Return $q$ \EndIf
  \If{$q$ is in the cache} \State \Return the cached node \EndIf
  \State $A \gets \{\, v \mapsto \Call{Saturate}{d, p + 1} \mid (v, d) \text{ on the spine of } q \,\}$ \Comment{children first}
  \State $F \gets$ the values of $A$ \Comment{values whose continuation still has to be fired}
  \While{$F \neq \emptyset$}
    \State remove the oldest value $i$ from $F$
    \ForAll{$e \in E_p$}
      \ForAll{$(j, f) \in \Call{FireTop}{e, i, A(i), p}$} \Comment{$f$ is already saturated at position $p+1$}
        \If{$j \notin A$}
          \State $A(j) \gets f$ ; add $j$ to $F$
        \ElsIf{$A(j) \neq f$}
          \State $u \gets \Call{Union}{A(j),\ f}$
          \If{$u \neq A(j)$} \State $A(j) \gets u$ ; add $j$ to $F$ unless it is in $F$ \EndIf
        \EndIf
      \EndFor
    \EndFor
  \EndWhile
  \State $n \gets$ the node with the values of $A$ as its spine, built once \Comment{from the largest value to the smallest}
  \State add $q \mapsto n$ to the cache
  \State \Return $n$
\EndFunction
\end{algorithmic}
```

Reading the pseudocode top to bottom is the argument for correctness. After the first
line, every continuation in $A$ is closed under all events *below* $p$, because no event
with $\Top > p$ touches position $p$ and the children were saturated. Every $f$ that
`FireTop` returns is closed under those events as well, so a union of two of them is too,
and $A$ stays closed while it grows. The `while` loop additionally closes it under $E_p$.
Only the values whose continuation changed are fired again, which is the paper's
*pipelining*. The set only grows and is bounded by the reachable states, so the loop
terminates.

**Worked example.** Let $K = 2$, and start from $\{(0,0)\}$.
Event $a$ has $\Top = \Bot = 1$ and moves position 1 from 0 to 1. Event $b$ has
$\Top = 0$: it moves position 0 from 0 to 1, and only if position 1 currently
holds 1 (a read-only position below the top).

* `Saturate` descends to position 1 first. There $a$ fires, so that node becomes
  $\{0, 1\}$, and the node for position 0 is built with it as its child from the
  start: $\{0 \mapsto \{0, 1\}\}$, instead of pointing at $\{0\}$ first and being
  replaced later.
* At position 0, $b$ fires from value 0. Its continuation is the saturated node $\{0,1\}$,
  and the event keeps only the branch with position 1 equal to 1, so the result is
  $(1, \{1\})$. Added to $A$, it becomes $\{0 \mapsto \{0,1\},\ 1 \mapsto \{1\}\}$.
* Value 1 is put on the frontier and fired again, but $b$ has no entry for it. Done:
  $\{(0,0), (0,1), (1,1)\}$.

A breadth-first schedule would instead have built the three sets $\{(0,0)\}$,
$\{(0,0), (0,1)\}$ and $\{(0,0), (0,1), (1,1)\}$ as separate diagrams.

### Firing an event out of one value

`FireTop` fires an event $e$ with $\Top(e) = p$ out of a *single* value $i$ of the
node that is being saturated, whose continuation is $A(i)$. The first value of the
event's `meta` at $p$ is never "not in the relation", so there are three cases,
which are the first meta level of the ordinary relational product restricted to one
source value:

| Meta at $\Top(e)$ | Meaning | Pairs $(j, f)$ that are produced |
|---|---|---|
| read only | position is read, not written | if the relation has an entry $i$: $(i,\ \textsc{SatRecFire}(A(i), \text{rel}_i, \dots, p+1))$ |
| write only | position is written, not read | for every value $j$ of the relation: $(j,\ \textsc{SatRecFire}(A(i), \text{rel}_j, \dots, p+1))$ |
| read of a read/write pair | read *and* written | find the entry $i$, then for every $j$ under it: $(j,\ \textsc{SatRecFire}(A(i), \text{rel}_{i,j}, \dots, p+1))$ |

Below $\Top(e)$ the event has to be applied to the continuation, and every node built
there has to come out saturated, because it may be used as a child later:

```math
\begin{algorithmic}[1]
\Function{SatRecFire}{$q, R, m, l$}
  \If{$m = \mathit{true}$} \State \Return $q$ \Comment{below $\Bot(e)$: identity, and $q$ is saturated already} \EndIf
  \If{$q = \emptyset$ or $R = \emptyset$} \State \Return $\emptyset$ \EndIf
  \If{$(q, R, m)$ is in the cache} \State \Return the cached node \EndIf
  \State $x \gets \Call{RelationalProductStep}{q, R, m}$ \Comment{recurses into \textsc{SatRecFire} at $l+1$ and \textsc{RecFire} at $l$}
  \State $y \gets \Call{Saturate}{x, l}$
  \State add $(q, R, m) \mapsto y$ to the cache
  \State \Return $y$
\EndFunction
\end{algorithmic}
```

`RecFire` is the same step for a continuation that stays at position $l$: the rest of a
spine, or the write half of a read/write pair. It does not saturate and is not
cached, because the node it contributes to is not finished yet, and it is a linear
walk along one spine.

!!! warning "Never saturate at $\Top(e)$ from `FireTop`"
    If firing also saturated its own result at position $p$, a firing that
    reproduces $q$ would call `Saturate(q, p)` while `Saturate(q, p)` is still on the
    stack, and never terminate. The paper splits `SatFire` from `SatRecFire` for
    exactly this reason. Everything that `SatRecFire` saturates is at a position
    strictly below $p$, so it is strictly smaller than the node in progress and
    cannot be it.

## Doing it without mutating nodes

The paper's implementation updates nodes in place and redirects the incoming arcs.
oxidd cannot do that: nodes are hash-consed and shared by every diagram in the
manager, and creating a node is a pure `get_or_insert`. The fork therefore keeps the
node in progress *outside* the diagram, and builds it once:

* The accumulator $A$ is a sorted `Vec` of `(value, continuation)` pairs. A fired
  pair $(j, f)$ is united into the *continuation* of $j$, $A(j) \cup f$, and nothing
  else is touched. When $f$ is already contained in $A(j)$, which is what happens
  in about 85% of the cases, the union returns $A(j)$ and builds no node at all. Values
  that were not in the node are inserted at their sorted position.
* The node is built once, at the end, from the largest value to the smallest, which
  is the order in which an ascending spine can be built without a union. The `Vec` is
  a stack in the shared `Scratch`, so this does not allocate per node either.
* Unions do not need saturating. Relational images distribute over union, so
  $N^*(X \cup Y) = N^*(X) \cup N^*(Y)$: the union of two saturated sets is
  saturated. That is what lets `Saturate` install a fired subtree into $A$ without
  another recursive call.
* What is lost compared to true mutation is that every version of a *continuation*
  that is still converging is a real entry in the unique table until it is garbage
  collected. That changes constants, not the *live* size, see
  [Memory](#memory-and-garbage-collection).

!!! warning "Do not use the node as the accumulator"

    Uniting into a node, and saturating a spine as "the saturated tail, with the head
    in front of it", looks simpler, and it avoids the accumulator. It was implemented
    first, and it is several times slower and creates several times as many nodes.
    Measured on the `anderson.6` example, the accumulator against the node-based
    version, which does the *same number of firings and merges* (about 2.3 to 2.5
    million):

    | | accumulator | node as accumulator |
    |---|---:|---:|
    | nodes in the manager after saturating (the result has 49,037) | 0.67M | 2.60M |
    | `Saturate` bodies (cache misses) | 153k | 787k |
    | merge = union on a node, nodes created | – | 1.32M |
    | merge = union on a continuation, nodes created | 0.37M | – |
    | `head ∪ tail` unions, nodes created | – | 0.60M |
    | time | about 2 s | about 4 s |

    Two things go wrong:

    * **A merge into a node is much more expensive than a merge into a continuation.**
      `Union(n, (j, f, ∅))` first builds the single-entry node, and then walks and
      rebuilds the spine of $n$ up to $j$, while the continuation of $j$ is all that
      changes. The merges are the same, and 85% of them change nothing, but each of them costs
      the single node and a walk over the spine, and each one that does change
      something leaves a copy of the spine prefix behind.
    * **Saturating the tail first saturates every suffix of every spine on its own.**
      Each suffix is a memoised call with its own fixpoint and its own intermediate
      spine. The values of the head can still write to the tail, so the head has to be
      united with an already saturated tail (`head ∪ tail`, 338k times here, which is
      a quarter of everything that is built), and a value whose continuation grows
      because of the head has to be fired again, on a continuation that is superseded
      once more by the next head. The accumulator has every value of the spine in it
      from the start, so a value that receives a result before it has fired fires once,
      on the merged continuation.

### Sharing the relational product

Below $\Top(e)$ firing an event is an ordinary relational product, so the five-case
analysis over `meta` is not duplicated. `relational_product_step` in
`oxidd-rules-ldd/src/apply.rs` does one level of it, and asks a
`RelationalProductRecursion` how to continue. There are two implementations:

| | Continuation `Next` (result at the next position) | Continuation `Same` |
|---|---|---|
| `CachedRecursion` (plain product) | cached `apply_relational_product` | cached `apply_relational_product` |
| `FireRecursion` (saturation) | `sat_rec_fire` at $l+1$, cached and saturating | `rec_fire`, uncached, not saturating |

So the plain relational product and the firing in saturation cannot drift apart, and
the scratch buffers of the saturation (below) are reachable from the trait
implementation instead of being passed through the shared step.

### No allocation in the recursion

`saturate` and `sat_rec_fire` are mutually recursive and can nest $O(K)$ deep each.
The buffers they need (the accumulator $A$, the frontier $F$, and the list of fired
pairs) are three `Vec`s in a `Scratch` that is created once per call. They are used as stacks: a call remembers
their length on entry, only touches what is above it and truncates back before it
returns. The information that stays the same during a run (the events) is in a
`Saturation` struct, so that stack frames stay small.

## Caching and the saturation cache

Two operators are cached, next to the existing ones (slots are the operands and the result):

| Operator | Key | Result | Slots |
|---|---|---|---|
| `Saturate` | node $q$ | node | 2 |
| `SatRecFire` | nodes $q, R, m$ | node | 4 |

`Saturate` also records `result → result`, since a saturated node is its own
saturation and a later call that reaches it directly should hit. The apply cache of the
LDD manager has five slots per entry, which is what `RelationalPredecessor` (four nodes
and a result) needs: with the earlier capacity of four it silently never stored
anything.

The **events are not part of the key**. Node identity does not change when a group's
relation grows, so a node that was cached as saturated under an older, smaller
relation would be reused as if it still were, giving a silently wrong (too small)
answer. So the contract is:

> Whenever any event's relation may have changed since the previous `saturate`
> call on this manager, call `LDDFunction::clear_saturation_cache` first.

`clear_saturation_cache` removes the entries of these two operators and keeps the
rest. Only `Saturate` and `SatRecFire` depend on the events. `Union`, `Project`,
`RelationalProduct` and the other operators are functions of their operand nodes
alone, and saturation is union-heavy, so those entries are worth keeping across
rounds. It is a sweep over the cache, comparing the operator of each occupied entry,
which is cheap next to a `saturate` call. The cache implementation is direct-mapped
with the operator stored in the entry, so a selective clear needs no extra
bookkeeping; the apply cache trait gained a `clear_operators(predicate)` for it.

An alternative was an `epoch` operand in the key, bumped whenever the events change,
so that entries of older events never match. That needs no sweep, but it puts a
numeric slot in both keys, which raised the entry size of the whole manager from five
to six slots, leaves the stale entries
in the cache until they are overwritten, and makes uniqueness the caller's
problem: two explorations that share a manager and both start counting at zero would
silently reuse each other's entries. Clearing has none of these, and forgetting it
is the same mistake as forgetting to bump the epoch. Note that the cache is emptied
before every garbage collection anyway, so on a run that is big enough to collect,
the reuse is bounded by the interval between collections either way.

## The driver: relations are learned on the fly

An LPS does not come with its transition relation. `learn_successors` enumerates
the successors of the states that have been seen and adds them to each group's
relation, and new local values are interned as they are found. Inside one
`saturate` call no new value can appear, because firing only installs values that
occur in an already learned relation; new values and transitions appear only
between calls. So the driver alternates:

```text
states = initial_states ; saturated = false
loop:
    changed = any group.learn_successors(states) changed its relation
    if not changed and saturated: break   # states is closed under exactly these events
    clear_saturation_cache()              # the events differ from the previous call
    states = saturate(states, events)
    saturated = true
```

Two properties keep this cheap and correct:

1. **The saturation cache is cleared before the call that uses the grown relation, and
   only then.** Whether a relation changed is an $O(1)$ check: hash-consing makes
   equal sets the same edge. The first round clears too, because the manager may have
   been used for another exploration.
2. **A round that learns nothing is the last one.** `states` is the output of the
   previous `saturate`, so it is closed under the events of that call; if learning
   added nothing, those are still the events, and the loop stops *without* calling
   `saturate` again. Conversely, a round that changed a relation can never be the
   last, since the states it discovered may enable transitions that are not learned
   yet. For pregenerated relations (the Sylvan fixtures), `learn_successors` does
   nothing, and the first call is the only one.

The number of `saturate` calls is thus the number of relation-changing rounds. This is
a coarse `Confirm` in the paper's terms: it learns per whole state set and per group,
instead of per newly touched local state, so it enumerates more than necessary.
It is correct and terminates because both `states` and every relation only grow in a
finite lattice.

**Deadlocks** are detected after the fact: for every group one
`remove_states_with_successor` pass over the final state set, which leaves the
states that no group can leave.

## Memory and garbage collection

Saturation produces *more* garbage than the other strategies, by construction:
every time the continuation of a value of a node that is still converging obtains a
better union, the superseded version is a dead, but still interned, entry of the unique
table. On the `anderson.6` example the result has 49,037 nodes, while saturating it
creates about 0.67 million, more than 90% of which are garbage. Nothing
is removed from the table until the manager collects garbage. With oxidd's
`manager-pointer` backend that never happens, and a large industrial model took
hours for individual rounds, with the operation counts of those rounds only a few times
those of the fast ones: the per-operation cost had grown because every lookup went into an
ever growing table. With the default `manager-index` backend, which starts a
collection in the background at 95% of the capacity, the same rounds took minutes,
with identical state counts. So:

* merc's `oxidd` dependency must not enable `manager-pointer`.
* The capacity of `manager-index` is a hard limit, not a hint. Size
  `--oxidd-node-capacity` for the *peak of live nodes* with headroom (the model
  above needed a few hundred million), not for the final diagram size.
* The `metrics` cargo feature logs `manager.num_inner_nodes()` and the statistics
  of the operation caches once per round. That is the way to compare peak sizes of
  strategies, more than the wall-clock time.

## Limitations

* **Sequential.** The recursion cannot be expressed with oxidd's `Recursor`
  abstraction, and the node-local fixpoint is inherently sequential; the
  multi-threaded manager dispatches to the same sequential code.
* **Stack depth.** $O(K^2)$ frames in the worst case, which is fine for $K$ in the
  low hundreds, and worth a deliberate check on wider models.
* **Coarse learning.** See above; a real `Confirm` needs a new `TransitionGroup`
  entry point for learning per position and value, and confirmed/unconfirmed
  bookkeeping.
* **The trailing action position.** A group's relation carries an extra
  action-label position that `meta` does not cover. Like the relational product,
  `SatRecFire` stops when `meta` runs out and never reads it.

## Testing

* `test_reachability_strategies_agree` and `test_reachability_detect_deadlocks` run
  the strategies against each other (`anderson.4` and a line LTS), and the `GridLps`
  tests run all of them on a model whose relations have to be learned.
* In the fork, a randomised differential test compares `saturate` against
  iterating union and relational product to a fixed point, over random events with
  random read/write patterns, which is the cheapest way to exercise the three
  `meta` cases at the top.
* `saturation_peak_benchmark` prints the peak and final node counts of every
  strategy per fixture. It prints and does not assert, so nothing guards against a
  regression that turns saturation back into a breadth-first search.
