# Parsing conditions

Two real specifications in `examples/mCRL2/` —
[`MLV.mcrl2`](https://github.com/MERCorg/merc/tree/main/examples/mCRL2/industrial/MLV)
and
[`garage-ver.mcrl2`](https://github.com/MERCorg/merc/tree/main/examples/mCRL2/industrial/garage)
— did not finish parsing in `merc_syntax`: one hung, the other stack-overflowed
the process. Both parse and linearize with the reference mCRL2 toolset
(`mcrl22lps`) in under a second, so this was never a problem with the
specifications; it is a consequence of the way pest's PEG backtracking
interacts with the if-then(-else) rules of `ProcExpr`. This page describes the
two independent causes, defines the condition positions that the parser marks
before parsing (Definition 1), and states why marking them is linear and safe
(Theorems 1 and 2).

## The shared-token ambiguity

`ProcExprIfThen` and `ProcExprIf` both start by parsing a `DataExpr` and
looking for a trailing `->`:

```
ProcExprIfThen = { DataExpr ~ "->" ~ ProcExprNoIf ~ "<>" }
ProcExprIf     = { DataExpr ~ "->" }
```

`DataExprInfix` includes `+`, `.` (`DataExprAt`) and `||` (`DataExprDisj`) —
the *same tokens* `ProcExprInfix` uses for choice, sequential composition, and
parallel composition. pest's `*`/`+` repetition is possessive: once `DataExpr`
commits to reading `a1(1) + a2(2) + a3(3)` as one big data expression, it
never backtracks into a shorter match — it walks the *entire*
`+`/`.`/`||`-joined run before discovering there is no `->` at the end and
failing outright.

That walk is retried at **every operand position** of the enclosing chain,
because it has to be: `a + (b -> P <> Q)` is legitimate mCRL2, so the if-check
genuinely needs attempting at each of the *n* positions in an *n*-term chain.
At position *i*, a doomed attempt costs O(*n* − *i*); summed over every *i*
that is O(*n*²) — and for long `.`/`||` chains, which build stack depth per
operand rather than an iterative loop, the recursion overflows the stack before
it even finishes being slow.

## The second, independent blow-up

Fixing the above is not enough on its own. Once a condition and its `->` are
genuinely found, `ProcExprIfThen` is attempted first and parses the whole
`then` branch (`ProcExprNoIf`) looking for a `<>`. `ProcExprNoIf`'s repetition
is possessive and greedy exactly like `DataExpr`'s, and every subsequent
condition it walks past recursively attempts the same thing, so a chain of *n*
if-without-`<>` terms is not O(*n*²) but exponential — the same recurrence
shape as naive recursive Fibonacci:

```
proc P(v: Nat) =
    (v == 0) -> a0(v).P(v)
  + (v == 1) -> a1(v).P(v)
  + (v == 2) -> a2(v).P(v)
  + ...                        // n terms, every condition genuinely marked, no fallback needed
;
```

Measured with every condition already correctly identified (i.e. isolating
this cause from the first one): *n* = 10 takes 165 ms; *n* = 20 does not finish
in 3 s; *n* = 640 overflows the stack. This is exactly the shape of
`MLV.mcrl2`'s `ConfigurationMemory` process — a long `+`-chain where every
term is its own bare (no-`<>`) condition.

Packrat memoization would only help with this second cause. The first one
comes from a single attempt walking forward through O(*n* − *i*) tokens inside
`DataExpr`'s own flat repetition, not from the same `(rule, position)` pair
being asked twice, so there is nothing to reuse.

## The workaround: marking conditions

<a id="def-condition-position"></a>**Definition 1 (condition position).** In a `proc` or `init` section, an
*operand position* is a position where a process operand can start, in a bracket
context that contains process expressions: the top level, a process bracket, or
the operand of `block`, `allow`, `hide`, `rename` or `comm`. An operand position
is a *condition position* if the maximal run of tokens that a `DataExpr` could
consume from there ends in `->`. It is an *if-then-else position* if moreover
that `->` is closed by a `<>` at the same bracket depth, where every `<>` closes
the nearest preceding unclosed condition of its bracket depth.

The maximal run is approximated on the token level: `[...]` and `{...}` groups
are skipped as a whole, and so is a `(...)` group, unless it cannot be data, that
is, it contains `=` (a process assignment such as `P(x = 1)`), `->`, `<>`, `sum`,
`dist`, `|`, `||_`, `<<` or `@`, is empty, or contains such a group itself; such a
group ends the run. Process keywords also end the run, except `tau` and `delta`,
which the grammar's `Id` accepts. A pending condition can no longer be closed
by a `<>` once its bracket closes or a `;` is reached.

Before the text is handed to pest, one left-to-right scan inserts a
Private-Use-Area codepoint at every condition position: `'\u{E000}'`, or
`'\u{E001}'` at an if-then-else position. The grammar requires the first marker
before `ProcExprIf` and the second before `ProcExprIfThen`, so a position that is
not a condition fails in constant time instead of walking the chain, and a bare
condition never attempts the `ProcExprNoIf ~ "<>"` tail. Both codepoints are
silent rules in the grammar, so they never appear in the syntax tree, and mCRL2
source cannot contain them.

<a id="thm-linear-scan"></a>**Theorem 1 (linear scan).** The scan that places the markers takes time linear in
the length of the text.

*Proof idea.* The scan visits every token once. A run that fails to end in `->`
is remembered per bracket depth, so the operand positions inside it are not
scanned again; bracket groups are skipped by matching brackets; and every
condition is pushed onto, and popped from, the stack of pending conditions at
most once.

<a id="thm-markers-are-safe"></a>**Theorem 2 (markers are safe).** If the marked text parses, its syntax tree is
the syntax tree that the grammar without markers assigns to the original text.

*Proof idea.* The markers only *gate* the condition rules: a marker never makes a
production succeed that would otherwise fail, it only makes the condition rules
fail early at unmarked positions. A misplaced or missing marker can therefore
only cause a parse error, never a different tree. Since the grammar cannot parse
conditions without markers, there is no fallback to the unmarked text: a gap in
the scan shows up as a parse error, whose position refers to the marked text.

Both theorems are argued on paper; they are not formalised. All example
specifications in `examples/mCRL2/` parse with the markers.

### Spans

Inserting a marker shifts every later byte offset by its length, three bytes in
UTF-8. After parsing the marked text, every span of the result is mapped back to
the original text: an offset is reduced by the marker length for every marker
that precedes it. This is the general form of the rebasing used for imports (see
[Source maps and imports](source_map.md)), done by the same trait
[`OffsetSpans`](https://mercorg.github.io/merc/merc_syntax/),
so no code that computes spans needs to know about the markers.

### Result

Parse times through `UntypedProcessSpecification::parse` (debug build). Neither
specification finished before the markers were added:

| Input                                             | Time   |
|---------------------------------------------------|--------|
| `MLV.mcrl2`                                       | 81 ms  |
| `garage-ver.mcrl2`                                | 139 ms |
| *n* = 640 chain of bare conditions (as above)     | 130 ms |
| *n* = 1280                                        | 331 ms |
| *n* = 2560                                        | 692 ms |

Both specifications are part of the example test suite, and a 200-term chain of
conditions and the dangling-else pairing have unit tests. No test checks the
timing itself, so a regression to quadratic or exponential behaviour would only
show up as a slow or hanging test run.

### Alternatives considered

- **Driving pest's generated rule functions by hand.** The plan was to keep
  the source text unchanged: write `ProcExpr`/`ProcExprPrefix` by hand, call
  pest's generated functions for every other rule, and gate `ProcExprIf` with
  a precomputed table. That does not work. `pest_generator` (2.9) emits the
  per-rule functions in a `rules` module inside the generated `parse`
  function, so no other code can call them.
- **Packrat memoization.** pest has none. An
  [unmerged pest 2.x experiment](https://github.com/pest-parser/pest/discussions/1081)
  caches failures in `ParserState::rule`, but silent (`_{ }`) rules such as
  `DataExprPrimary` and `DataExprInfix` never call `rule`, and that is where
  the repeated work of the first cause happens. In
  [pest3](https://github.com/pest-parser/pest3), memoization only covers
  left-recursive rules, and `ProcExpr`/`DataExpr` are not left-recursive.
- **Switching parser generator** (e.g. `peg`, which has `#[cache]`): too large
  a change for this problem.

## Why `ProcExprNoIf` stays

`ProcExprNoIf` is currently identical to `ProcExpr` in its primaries and
infixes; one might merge them and make `<>` a flat infix token handled by the
Pratt parser. That does not reproduce what the real mCRL2 toolset does, which
was verified directly against `mcrl22lps` (using `--no-constelm` so the boolean
parameters are not constant-propagated away before the guards can be compared).
mCRL2's own grammar has the same `ProcExprNoIf`/`ProcExpr` split (the textbook
"matched statement" rule for dangling-else; see
[the process expression grammar](https://mcrl2.org/web/user_manual/language_reference/process.html)
and [mCRL2org/mCRL2#917](https://github.com/mCRL2org/mCRL2/issues/917), where
merging the two was rejected), and merc's precedence table already matches it.

Whether the `then` branch widens across `+` depends on whether a matching `<>`
exists later in the input — a lookahead-dependent decision no static precedence
value can express:

```
proc P(x, y: Bool) = x -> y -> a <> b;
```

parses identically — same guard on `b`, `x && !y` — to `x -> (y -> a <> b)`, not
`x -> (y -> a) <> b`, and

```
proc P(x, y: Bool) = x -> y -> a <> b <> e;
```

parses identically to `x -> (y -> a <> b) <> e`: the *first* `<>` closes the
*most recently opened* condition, the second closes `x`'s. This is exactly the
pairing of Definition 1, and it is why `ProcExprNoIf` must keep
recognizing a bare nested condition inside a `then` branch even though mCRL2's
documentation says no if-then productions are allowed there: the shipped
`mcrl22lps` accepts it. A `<>` inside a nested `(...)` only closes a condition
inside those same parentheses. The second example is a unit test.

See also [Precedence](precedence.md), which
verifies a *different* class of parser disagreement the same way — against the
actual `mcrl22lps`/dparser behavior rather than the documented grammar.
