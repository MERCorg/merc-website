# The Set Automaton

`merc_sabre` — the **S**et **A**utomaton **B**ased **R**ewrit**e** engine — finds
every left-hand side that matches *anywhere* in a term in a single automaton
walk, rather than trying each rewrite rule against each subterm in turn. The
construction is based on

> Erkens, R., Groote, J.F. (2021). *A Set Automaton to Locate All Pattern
> Matches in a Term*. In: Theoretical Aspects of Computing – ICTAC 2021.
> [DOI](https://doi.org/10.1007/978-3-030-85315-0_5)

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

### A worked example: `+` on machine-word `Pos`

`merc`'s machine-word encoding gives `Pos` addition six equations:

```
(@most_significant_digit(w1) + @most_significant_digit(w2)) = ...;
(@concat_digit(p1,w1)        + @most_significant_digit(w2)) = ...;
(@most_significant_digit(w1) + @concat_digit(p2,w2))        = ...;
(@concat_digit(p1,w1)        + @concat_digit(p2,w2))        = ...;
(@succ_pos(p1) + p2) = @succ_pos((p1 + p2));
(p1 + @succ_pos(p2)) = @succ_pos((p1 + p2));
```

The first four match on the digit mappings `@most_significant_digit`/
`@concat_digit`, one case per combination of one-digit/multi-digit operand.
The last two exist because, in this encoding, `Pos`'s actual *constructors*
are `@c1` and `@succ_pos` — the digit mappings are only ever produced by
equations, so an unreduced `@succ_pos`-headed term can still legitimately
reach `+`, and these two equations are its home. Note their shape: each
constrains only *one* argument (`@succ_pos(p1)`, `@succ_pos(p2)`) and leaves
the other (`p2`, `p1`) a completely unconstrained variable.

Building the automaton starts by matching the root `+` symbol, which turns
each equation into a goal with one obligation per non-variable argument:

| equation | obligation at position 1 | obligation at position 2 |
|---|---|---|
| digit + digit | `@most_significant_digit(w1)` | `@most_significant_digit(w2)` |
| chain + digit | `@concat_digit(p1,w1)` | `@most_significant_digit(w2)` |
| digit + chain | `@most_significant_digit(w1)` | `@concat_digit(p2,w2)` |
| chain + chain | `@concat_digit(p1,w1)` | `@concat_digit(p2,w2)` |
| succ + * | `@succ_pos(p1)` | *(none — `p2` is a bare variable)* |
| * + succ | *(none — `p1` is a bare variable)* | `@succ_pos(p2)` |

All six goals still announce at `ε`, so `partition`'s root special case puts
them in one group — correct so far, the same one-time special case described
above. Now follow one branch: the construction tries symbol `@succ_pos` at
position 1. For the four digit-based goals this is a mismatch (discarded).
For "succ + *" it's a complete match — `@succ_pos(p1)`'s only child is a
variable, and that goal had no obligation at position 2 either, so the whole
equation is *completed* right here and becomes an announcement, not a goal
in the next state. For "* + succ" there was never an obligation at
position 1, so it carries forward unchanged, still holding only its
position-2 obligation.

The resulting state has exactly one live goal, whose sole obligation sits at
position 2 — the group's announcement position correctly shrinks away from
`ε`, and picking `@succ_pos` at position 2 first instead makes no
difference by symmetry. Six equations for `+`, on their own, settle in one
step; that's not yet a bug.

What *is* enough to get stuck is for one of these lopsided goals — one
operand pinned, the other a bare variable, its lone obligation left sitting
at just position 1 or just position 2 — to still be in a group the next time
the construction discovers a fresh subtree belonging to some *other*
equation whose own obligation happens to sit at the sibling position. The
old code decided whether to fold that fresh subtree into an existing group
by testing it against the group's **announcement** positions, and a group
holding one of these lopsided goals still announces at `ε` — because
`greatest_common_prefix` can't produce a common prefix longer than `ε` while
one member constrains position 1 and nothing else in that partition
constrains position 1 at all. Since `pos_comparable(ε, anything)` is always
`true`, such a group is a standing invitation: the next fresh subtree the
construction meets, from whichever equation, gets folded in rather than
started fresh, widening the group's positions again and leaving it just as
open at `ε` for another round. Repeated across a whole specification where
`+`, `<`, `==`, `*`, … on `Pos` and `Nat` all repeat this same "succ + *"
shape, there is always another candidate goal ready to keep some group open
— exactly what the fix's own comment describes: such a partition "absorbed
every subsequent fresh subtree without bound," so the construction's
worklist never drained.

### Why this doesn't happen with the ordinary binary rules

The `Binary` encoding's `Pos` addition — `@addc` in
[`pos.mcrl2`](https://github.com/MERCorg/merc/blob/main/crates/syntax/spec/pos.mcrl2) —
has equations with the same superficial shape (`@addc(false,@c1,p) = succ(p)`
leaves `p` unconstrained, just like `@succ_pos(p1) + p2` does above), so a
transient `ε`-glued group can form there too. What it doesn't have is a
*second* representation to keep re-triggering that shape. `Pos`'s
constructors in `Binary` mode are `@c1` and `@cDub` — the same pair every
equation is written against, with no generic-constructor counterpart layered
on top: `succ` is only ever a plain mapping, fully defined by its own closed
equations over `@cDub`, and it never appears as an argument pattern inside
`+`'s own left-hand sides. So once `@addc`'s handful of equations have been
told apart, every surviving goal ends up needing the same one remaining
position, the group's announcement position shrinks for good, and it stops
being a magnet for unrelated subtrees.

`Pos` (and `Nat`) under `MachineWord`, by contrast, keep `@succ_pos`
(`@succ_nat`) as a real constructor *alongside* the digit mappings precisely
so that a not-yet-normalized term built the generic way still has somewhere
to go — which means **every** arithmetic and comparison operator on these
sorts (`+`, `<`, `==`, `*`, …) needs its own "succ + *" / "* + succ" pair the
way `+` does above. With one shared automaton covering the whole
specification, one persistently `ε`-anchored group anywhere is enough:
"absorbed every subsequent fresh subtree without bound," as the fix's own
comment puts it, is exactly what happens when the merge test can't tell a
group that has genuinely settled from one that's still open at the root.

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