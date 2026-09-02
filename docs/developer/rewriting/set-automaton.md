# The Sabre set automaton

`merc_sabre` — the **S**et **A**utomaton **B**ased **R**ewrit**e** engine — finds
every left-hand side that matches *anywhere* in a term in a single automaton
walk, rather than trying each rewrite rule against each subterm in turn. The
construction is based on

> Erkens, R., Groote, J.F. (2021). *A Set Automaton to Locate All Pattern
> Matches in a Term*. In: Theoretical Aspects of Computing – ICTAC 2021.
> [DOI](https://doi.org/10.1007/978-3-030-85315-0_5)

This page describes the moving parts of the construction —
[`SetAutomaton::new`](https://github.com/MERCorg/merc/blob/main/crates/sabre/src/set_automaton/automaton.rs) —
and a correctness fix to it, made while wiring up
[`NumberEncoding::MachineWord`](machine-numbers.md), that is worth
understanding before touching this code again.

## Goals, obligations, announcements

Every state of the automaton carries a set of `MatchGoal`s — one per rewrite
rule that could still fire from here:

```rust
pub struct MatchGoal {
    pub obligations: Vec<MatchObligation>,
    pub announcement: MatchAnnouncement,
}

pub struct MatchObligation {
    pub pattern: DataExpression,
    pub position: DataPosition,
}

pub struct MatchAnnouncement {
    pub rule: Rule,
    pub position: DataPosition,
    pub symbols_seen: usize,
}
```

- An **obligation** is a sub-pattern of the rule's left-hand side that still
  needs checking, pinned to the position in the term it must hold at. Every
  goal starts with exactly one obligation — the whole left-hand side at the
  root, position `ε`.
- The **announcement** position is where the goal itself is anchored — the
  position at which the rule fires once every obligation is satisfied. It
  also starts at `ε`, and only ever moves by having a common prefix stripped
  off once the automaton has actually distinguished this rule from its
  neighbours (see below).

Building the automaton is a fixpoint computation over states. For a state
and a head symbol, `State::compute_derivative` sorts each of the state's
goals into:

- **completed** — the one remaining obligation *is* the symbol at this
  position, with only variables below it. The goal becomes an output
  (`Transition::announcements`) rather than part of any destination state.
- **discarded** — an obligation at this position expects a *different* head
  symbol. Dead end, dropped.
- **unchanged** — no obligation is pinned to this position at all; the goal
  carries forward untouched.
- **reduced** — an obligation *is* pinned here and its symbol matches; it's
  replaced by one fresh obligation per non-variable argument, one level
  deeper.

The unchanged and reduced goals become the raw material for whatever state(s)
this transition leads to.

## Partitioning goals into destination states

A single transition doesn't have to lead to one destination. Goals whose
remaining obligations sit under disjoint subtrees can be split across several
independent destinations — doing so lets
[`MatchGoal::greatest_common_prefix`](https://github.com/MERCorg/merc/blob/main/crates/sabre/src/set_automaton/match_goal.rs)
factor a longer common position prefix out of each group, which keeps that
destination's label (and thus how much lookahead is needed before the
automaton can say anything useful) tighter.

`MatchGoal::partition` groups goals by whether their *announcement*
positions are "comparable" — one a prefix of the other:

```rust
/// Checks for two positions whether one is a subposition of the other.
/// For example 2.2.3 and 2 are comparable. 2.2.3 and 1 are not.
pub fn pos_comparable(p1: &DataPosition, p2: &DataPosition) -> bool
```

`pos_comparable` treats the *empty* position as comparable to anything — it
returns `true` the moment either position runs out of indices to compare. At
the very start of a match, before any rule has been distinguished from its
siblings, every goal's announcement position is still `ε`; `partition`
special-cases this ("if one of the goals has a root position, all goals are
related") and puts everything in one group. That's correct and cheap: it
happens once, doesn't recurse, and doesn't grow.

Separately, a transition also introduces *fresh* subtrees — the argument
positions the head symbol's arity adds — each of which gets one brand-new
goal per rewrite rule, since that rule's pattern hasn't been looked at down
there yet. `State::derive_transition` has to decide, for each fresh position,
whether it belongs with one of `partition`'s existing groups or needs a
destination of its own. **This decision is where a real bug lived**, fixed
after being exposed by the machine-word work.

## The partition-merge bug

Until this fix, the fresh-subtree decision reused the same
announcement-position comparison `partition` uses internally — testing a
fresh position against the deduplicated announcement positions of each
group. That's unsound as a *repeated* test, because an announcement position
only shortens once every member of its group shares a longer common prefix,
and `greatest_common_prefix` forces that common length to `0` the instant
*any* member — announcement or obligation — is already sitting at `ε`. So a
group containing even one still-open, root-anchored goal keeps announcement
position `ε` pinned indefinitely, at every state reachable while that goal
survives, not only at the very first step. Since `pos_comparable(ε, _)` is
always `true`, such a group absorbed *every* fresh subtree from then on,
splicing in a fresh copy of every rewrite rule each time — so the state it
produced never matched one already built, the construction's worklist never
drained, and `SetAutomaton::new` never returned.

!!! note "Why this had gone unnoticed"
    The defect isn't specific to any one kind of rule — a group with a
    surviving root-anchored goal is unremarkable. What made it manifest as
    outright non-termination, rather than merely coarser grouping that still
    settles, was the recursive digit-chain shape of the `MachineWord`
    arithmetic rules (see [Machine Numbers](machine-numbers.md)): each round
    finds a genuinely new, deeper obligation position to fold in, so the
    worklist has something to keep growing forever rather than eventually
    running dry.

The fix swaps the test to use each group's remaining **obligation**
positions instead:

```rust
for goal in &group {
    for obligation in &goal.obligations {
        obligation_positions.push(obligation.position.clone());
    }
}
```

This is sound where the announcement-position version wasn't, because
obligations reaching this point are never empty by construction — a goal
with no obligations left is classified as *completed* and diverted to the
transition's announcements before this code ever sees it
(`compute_derivative` asserts exactly this). So `ε` only turns up among
obligation positions when a rule's pattern is *genuinely* still anchored at
the root — real, load-bearing overlap — never as a leftover from a rule that
was simply matched once, long ago, and never revisited. A fresh subtree now
only joins a group when one of that group's still-open obligations actually
sits under (or over) it, which is the condition the algorithm always meant
to test.

`MatchGoal::partition`'s own grouping rule — comparable *announcement*
positions, with the root-position special case — is unchanged; only the
downstream decision of whether to fold a newly discovered subtree into one
of `partition`'s groups moved from announcement positions to obligation
positions. The fix trades a documented amount of precision for guaranteed
termination: some fresh subtrees that could, in principle, have safely
shared a destination now start their own instead.

## Current status: `SabreRewriter` and `MachineWord`

Fixing the merge defect is a genuine correctness fix, but it is **not** the
same thing as making `SabreRewriter` practical on
`NumberEncoding::MachineWord` specifications. Re-running a minimal
`SabreRewriter` repro (`1 + 1` under `Nat`, `MachineWord` encoding) after the
fix shows construction no longer collapses into the single
ever-absorbing-partition symptom described above — but it still hadn't
reached a fixpoint after 45 seconds, with state and transition counts still
climbing (past 1,800 states and 25,000 transitions) for that two-token
expression. That looks like genuine combinatorial blow-up from the recursive
digit-chain pattern shape, a separate, still-open concern from the merge bug
this page describes.

!!! note "Use `InnermostRewriter` for `MachineWord`"
    Until that blow-up is addressed, prefer `InnermostRewriter` (or
    `NaiveRewriter`) over `SabreRewriter` when selecting
    `NumberEncoding::MachineWord` — see the note in
    [Machine Numbers](machine-numbers.md#native-evaluation-in-the-rewriter).

## References

- [`set_automaton/automaton.rs`](https://github.com/MERCorg/merc/blob/main/crates/sabre/src/set_automaton/automaton.rs),
  [`set_automaton/match_goal.rs`](https://github.com/MERCorg/merc/blob/main/crates/sabre/src/set_automaton/match_goal.rs)
- Erkens, R., Groote, J.F. (2021). *A Set Automaton to Locate All Pattern
  Matches in a Term*. [DOI](https://doi.org/10.1007/978-3-030-85315-0_5)
- Bouwman, M., Erkens, R. (2022). *Term Rewriting Based On Set Automaton
  Matching*. [arXiv](https://arxiv.org/abs/2202.08687)
