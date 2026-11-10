# Copy nodes for LDD transition relations

Plan for introducing Sylvan-style *copy nodes* into the LDD implementation of the oxidd fork
(`~/oxidd`, crate `oxidd-rules-ldd`) and using them for the grouped transition relations of
`merc_symbolic`.

Status: **design only, partially implemented.** A branch `ldd-copy-nodes` exists in `~/oxidd` with the
encoding groundwork (see [Current state of the branch](#current-state-of-the-branch)); the relational
product is untouched, so nothing works end to end yet. The analysis below comes from reading Sylvan's
`sylvan_ldd.c`, mCRL2's `summand_group.h` and the current `oxidd-rules-ldd` sources.

## Why

A transition group stores a short-vector relation `T' -> U'` over the positions it reads and writes
(`crates/symbolic/src/symbolic_lps_explore.rs`, `SymbolicLpsGroup::learn_successors`). When several
summands are joined into one group — the `used`, `simple` and custom strategies of
`crates/symbolic/src/summand_grouping.rs` — a member summand may leave a position untouched that the
group as a whole writes.

Today the member's transitions repeat the source value explicitly, and `transition_group_pattern()`
adds the position to the group's *read* set where that is needed to know the value. That is correct
(see below), but it materialises the identity, in two separate ways:

1. **An enlarged read set**, for custom groupings only. Under `used` and `simple` the closure never
   fires: members agree on the positions they use, so a member that does not write `p` must read it.
2. **A concrete value in the write slot**, which is the `used` case and the expensive one. A member
   that reads `p` but does not write it still has to carry a value there, so its transitions are
   duplicated once per value of `p`, and `learn_successors` enumerates it once per distinct read
   projection rather than once per projection on its own read positions.

With `k` values in the column the relation grows by a factor `k`, which is exactly the blow-up copy
nodes exist to avoid. They remove both effects: the write slot becomes "same as read", and the
compensating reads become unnecessary.

## Correctness of the current compensation

Copy nodes are an optimisation, not a correctness fix. The invariant that makes the compensating
reads sound is that for every member `i` of a group, `W ⊆ writes_i ∪ R`, where `W` is the group's
write set and `R` its read set. It holds by construction: take `p ∈ W`; either `i` writes it, or `i`
reads it (so `p ∈ R` from the union of the members' reads), or `i` neither reads nor writes it — and
that is exactly the case the closure loop in `transition_group_pattern()` adds to `R`.

Given that, every short vector stored during learning is exactly `(s↾R, s'↾W)` for a real transition
`s → s'` of a member:

- `full_state` agrees with the source state `s` on all of `R`, and `reads_i ⊆ R`, so by the
  `read_positions` contract both `prepare`'s applicability decision and `enumerate`'s successors for
  member `i` are the ones `s` really produces.
- For `p ∈ W` that `i` does not write, `next_state[p] = full_state[p] = s[p]` by the
  `StateEffect::Positions` contract, and `p ∈ R` guarantees `full_state[p]` really is `s[p]` rather
  than the leftover value the buffer was seeded with.

Nothing is over- or under-approximated: the relational product only fires entries whose read part
matches the source state, and a position a member leaves alone is written back with the value it had.
This is what `test_grouping_agrees_with_ungrouped` in `crates/symbolic/tests/symbolic_lps_test.rs`
checks, and it is the property the copy-node version has to preserve.

## Copy nodes in Sylvan

`3rd-party/sylvan/src/sylvan_ldd.{h,c}` in the mCRL2 checkout.

- **Meaning.** From `sylvan_ldd.h`: *"A copy node represents 'read x, then write x' for every x. In a
  read-write relation, use copy nodes twice, once on read level, once on write level."* On a read
  level a copy node matches **any** value of the set; on a write level it emits the value that was
  read.
- **Encoding.** A dedicated flag bit in the node (`mddnode_getcopy`: `n->b & 0x10000`,
  `mddnode_makecopy`), *not* a reserved value — the value field of a copy node is unused.
- **Position.** A copy node always sits at the **head** of a level's right spine
  (`lddmc_extendnode` keeps it first, `lddmc_follow` skips over it). The relational product relies on
  this: when it meets a copy node the set operand is still at the start of its own spine, so the copy
  can be applied to every value.
- **Scope.** Only `relprod`, `relprev` and `union` support copy nodes (`sylvan_ldd.h`). They occur in
  relations only, never in state sets.
- **Construction API.** `lddmc_make_copynode`, `lddmc_iscopy`, `lddmc_followcopy`, and the cube
  builders `lddmc_cube_copy` / `lddmc_union_cube_copy` / `lddmc_member_cube_copy`, which take a
  parallel `int* copy` array next to the `uint32_t* values`.
- **The mechanism that makes copy-on-write work.** In `lddmc_relprod`, the *read* level of a
  read+write pair (`m_val == 1`) recurses with the set operand **unchanged** ("stay same level of set
  (for write)"), and only the *write* level (`m_val == 2`) descends into `mddnode_getdown(n_set)`.
  So at the write level the set node is still the node at that state-vector position, and
  `if (mddnode_getcopy(n_rel)) value = mddnode_getvalue(n_set);` writes the read value.
- **Copy on a read level** (`m_val == 1` or `3`) spawns one sub-problem per value of the set and
  unions the results, plus the result of the remaining (non-copy) relation entries.

## How mCRL2 uses them

`libraries/lps/include/mcrl2/lps/lps_summand_group.h` builds, for every summand `i` in a group, a
`copy` vector over the group's *used slots* (`2j` for each read position `j` of the group, `2j+1` for
each written position):

```cpp
copy.push_back(read_write_patterns[i][j] ? 0 : 1);
```

So a slot is a copy slot exactly when the group uses that position in that role but the summand does
not. The vector is handed to `union_cube_copy` when the summand's transitions are added.

## Current state of oxidd

`~/oxidd/crates/oxidd-rules-ldd/src/apply.rs`:

- Meta values (`relation_product_meta`): `0` not in relation, `1` read-only, `2` write-only,
  `3` read of a read+write pair, `4` write of that pair. (Sylvan numbers these `0/3/4/1/2`.)
- `apply_relational_product` matches set and relation values with `set_value.cmp(rel_value)` and, in
  the `read_of_pair` branch, recurses with **`set_down`** — the set is descended at the read level.
  At the `write_of_pair` level the read value is therefore no longer reachable.
- Nodes carry a value of type `M::InnerNodeValue` (`u32` for the LDD manager) and no spare tag: the
  node layout lives in the generic managers (`oxidd-manager-pointer` / `-index`), so a Sylvan-style
  flag bit would mean changing oxidd-core's node representation.

## Plan for oxidd

### 1. Encoding: a reserved value, not a flag bit

Reserve one value as the copy marker (`u32::MAX`, which mCRL2 already burns as `relprod_ignore`) and
give `LDDValue` a `copy_value()` / `is_copy()` pair. Adding a real flag bit is the faithful port but
requires touching the node layout of both managers; the sentinel keeps the change inside
`oxidd-rules-ldd`. The cost is one unusable value per column, which merc must assert against when
interning (`SymbolicContext::columns`).

Because Sylvan requires copy nodes at the *head* of a spine while `u32::MAX` sorts last, spine
comparisons must use an `ldd_cmp` that orders the copy value before every other value — the natural
`Ord` must not be used on node values any more. Call sites to convert: `apply_union`, `apply_minus`,
`apply_intersect`, `project`, `apply_relational_product`, `apply_relational_predecessor`, and
`make_node`'s ordering assertion. Anything that iterates a relation's spine outside oxidd (merc's
`crates/symbolic/src/ldd/cube_iter_ldd.rs` and `convert_ldd.rs`) needs the same treatment or an
explicit rejection of copy nodes.

### 2. Restructure the read+write pair in `apply_relational_product`

Adopt Sylvan's convention: the `read_of_pair` branch keeps the set operand at the same level and lets
the `write_of_pair` branch descend it. Concretely:

- `read_of_pair` (meta `3`), non-copy: match `set_value` and `rel_value` as today, but recurse
  `(set, rel_down, meta_down)` instead of `(set_down, …)`.
- `read_of_pair`, copy: for every value of the set spine recurse `(set_at_that_value, rel_down,
  meta_down)` and union the results, then union with the result of `(set, rel_right, meta)` so the
  non-copy entries of the relation still apply.
- `write_of_pair` (meta `4`): recurse with `(set_down, rel_down, meta_down)` and emit `rel_value`, or
  `set_value` when `rel_value.is_copy()`.
- `read_only` (meta `1`), copy: match every set value, keep it in the output.
- `write_only` (meta `2`), copy: writes the source value of a position the group does not read; merc
  never produces this (a copy write always comes with the position in the group's read set), so
  reject it with a clear error rather than guessing.

The apply-cache key stays `(set, rel, meta)`, so caching remains sound; only which `set` edge is
passed at which level changes.

### 3. Mirror it in `apply_relational_predecessor`

`relprev` needs the same treatment (Sylvan's `lddmc_relprev`, `sylvan_ldd.c:1334` onwards, has a
four-way case split on read/write × copy). merc needs this for `--deadlocks`, which calls
`relational_predecessor` on the same relations.

### 4. API surface

- `LDDFunction::COPY` (or `copy_value()`) so callers can name the marker.
- `LDDFunction::cube_copy(manager, values, copy)` and `union_cube_copy(&self, values, copy)`,
  mirroring Sylvan. With the sentinel encoding these are thin wrappers over the existing `singleton`
  and `union`, but they document the contract and can validate that copies only appear on levels the
  meta marks as read or write.
- `is_copy` / `follow_copy` accessors for iteration code.

### 5. Tests in oxidd

- A copy node on a read+write pair reproduces the source value.
- A relation mixing copy and concrete entries at the same level.
- Equivalence: relation with copy nodes ≡ the explicitly materialised identity relation, over a set
  with several values per column (both `relational_product` and `relational_predecessor`).
- `union` of two cubes where one has a copy at a level the other has a concrete value.

`crates/oxidd/tests/ldd.rs` (untracked on the branch) is the natural home; it already has helpers for
building sets, metas and comparing results.

## Plan for merc

1. **`transition_group_pattern()`** (`crates/symbolic/src/summand_grouping.rs`) drops the
   compensating reads: the group pattern becomes the plain union of its members' patterns. The doc
   comment explaining the extra reads is replaced by the copy-node contract, and its unit test
   changes accordingly (group `[0, 2]` becomes `r-+` instead of `r++`).
2. **Per-summand copy vector.** In `SymbolicLpsGroup::learn_successors`, for each member summand
   compute, once at construction time, a copy flag per short-vector slot: read slot `k` is a copy iff
   the summand does not read `read_indices[k]`; write slot `m` is a copy iff the summand does not
   write `write_indices[m]`. This is exactly mCRL2's `copy` vector; store it next to `indices`.
3. **Building the relation.** Replace `LDDFunction::singleton(m, interleaved)` + `union` with
   `union_cube_copy(interleaved, copy)`. The write side then only fills the slots the summand
   actually writes; copy slots need no value from `next_state`.
4. **Interning guard.** Assert in `SymbolicContext` that a column never reaches `u32::MAX` values, so
   a real value can never collide with the copy marker.
5. **`.sym` I/O.** mCRL2 writes relations containing copy nodes into `.sym` files, so
   `crates/symbolic/src/ldd/io_symbolic_lts.rs` and the BDD conversion (`crates/symbolic/src/bdd/`)
   must either understand them or report an error instead of silently treating `u32::MAX` as a value.
   Worth checking against a `lpsreach --groups=used` output.
6. **Tests.** `crates/symbolic/tests/symbolic_lps_test.rs` already explores the same LPS under every
   grouping; extend it to assert that the grouped relations are *smaller* (fewer transition vectors)
   than the materialised ones, which is the whole point of the change.

## Risks and open questions

- **Sentinel vs. flag bit.** If a column ever legitimately needs `u32::MAX`, the sentinel breaks. The
  alternative is a newtype `InnerNodeValue` for LDDs with the copy marker in the top bit, which
  halves the value range but is checkable; the flag-bit port is the third option and the most work.
- **Ordering invariant.** Every spine comparison must move to `ldd_cmp`. A missed call site produces
  a silently malformed diagram rather than a panic, so the `make_node` debug assertion should be
  extended to check the copy-first invariant.
- **Read-only copy cost.** A copy on a read level spawns one sub-problem per value in the set, so it
  is not free; it pays off because the *relation* stays small, not because the product gets cheaper.
- **Write-only copy** is rejected above rather than implemented; revisit if a grouping strategy is
  added that writes a position no member reads.

## Current state of the branch

`~/oxidd`, branch `ldd-copy-nodes`, uncommitted:

- `crates/oxidd-rules-ldd/src/lib.rs`: `LDDValue::copy_value()`, `is_copy()` and `ldd_cmp()` with the
  copy-first ordering, plus the `u32` implementation.
- `crates/oxidd-rules-ldd/src/apply.rs`: three comparisons switched to `ldd_cmp`
  (`apply_union`, `apply_minus`, `apply_intersect`).
- `crates/oxidd/tests/ldd.rs`: new, untracked, currently covering the *existing* relational product
  and predecessor (no copy-node cases yet).

Not started: the relational product restructure (step 2), `relprev` (step 3), the public API
(step 4), the copy-node tests (step 5) and every merc-side change. The branch has not been built or
tested since the changes were made.
