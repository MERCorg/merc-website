# If-Then(-Else) Parsing Performance

Two real specifications in `examples/mCRL2/` —
[`MLV.mcrl2`](https://github.com/MERCorg/merc/blob/main/examples/mCRL2/industrial/MLV/MLV.mcrl2)
and
[`garage-ver.mcrl2`](https://github.com/MERCorg/merc/blob/main/examples/mCRL2/industrial/garage/garage-ver.mcrl2)
— did not finish parsing in `merc_syntax`: one hung, the other stack-overflowed
the process. Both parse and linearize with the reference mCRL2 toolset
(`mcrl22lps`) in under a second, so this was never a problem with the
specifications; it's a consequence of the specific way pest's PEG backtracking
interacts with `ProcExpr`'s if-then(-else) grammar. This page works through
the two independent causes, the fix, and an alternative design that looked
promising but turns out to conflict with how the real mCRL2 toolset itself
parses this construct — verified directly against it, not assumed.

## The shared-token ambiguity

`ProcExprIfPrefix`/`ProcExprIfThen` both start by parsing a `DataExpr`,
looking for a trailing `->`:

```
ProcExprIfPrefix = { DataExpr ~ "->" ~ (ProcExprNoIf ~ "<>")? }
ProcExprIfThen    = { DataExpr ~ "->" ~ ProcExprNoIf ~ "<>" }
```

`DataExprInfix` includes `+`, `.` (`DataExprAt`) and `||` (`DataExprDisj`) —
the *same tokens* `ProcExprInfix` uses for choice, sequential composition, and
parallel composition. pest's `*`/`+` repetition is possessive: once `DataExpr`
commits to reading `a1(1) + a2(2) + a3(3)` as one big data expression, it
never backtracks into a shorter match on its own — it walks the *entire*
`+`/`.`/`||`-joined run before discovering there's no `->` at the end and
failing outright.

That walk is retried at **every operand position** of the enclosing chain,
because it has to be: `a + (b -> P <> Q)` is legitimate mCRL2, so the if-check
genuinely needs attempting at each of the *n* positions in an *n*-term chain.
At position *i*, a doomed attempt costs O(*n* − *i*); summed over every *i*
that's O(*n*²) — and for long `.`/`||` chains (which build stack depth
per operand rather than an iterative loop), the recursion overflows the stack
before it even finishes being slow.

## The second, independent blow-up

Fixing the above is not enough on its own. Once a condition and its `->` are
genuinely found, `ProcExprIfPrefix`'s optional `(ProcExprNoIf ~ "<>")?` tail
is attempted *unconditionally*, to see whether this `if` has an explicit
`else`. `ProcExprNoIf`'s own repetition is possessive and greedy exactly like
`DataExpr`'s — and because *every subsequent condition it walks past while
looking for that `<>` recursively attempts this very same optional tail*, a
chain of *n* if-without-`<>` terms is not O(*n*²) but genuinely exponential —
the same recurrence shape as naive recursive Fibonacci, T(*n*) = T(*n*−1) +
T(*n*−2) + …:

```
proc P(v: Nat) =
    (v == 0) -> a0(v).P(v)
  + (v == 1) -> a1(v).P(v)
  + (v == 2) -> a2(v).P(v)
  + ...                        // n terms, every condition genuinely marked, no fallback needed
;
```

Measured with every condition already correctly identified (i.e. isolating
this cause from the first one): *n* = 10 takes 165 ms; *n* = 20 doesn't finish
in 3 s; *n* = 640 overflows the stack. This is exactly the shape of
`MLV.mcrl2`'s `ConfigurationMemory` process — a long `+`-chain where every
term is its own bare (no-`<>`) condition.

### Why plain memoization only fixes one of the two

It's tempting to reach for packrat memoization (cache each named rule's
result per start position) as a general PEG fix. It would eliminate the
second cause almost for free — that one is a textbook overlapping-subproblems
pattern, the same shape naive recursive Fibonacci has, and memoization is the
textbook fix for exactly that shape.

It would **not** eliminate the first cause, at least not without also
rewriting the grammar. Each `DataExpr`-at-position-*i* attempt is asked
*exactly once* per *i* — the cost comes from each individual attempt walking
forward through O(*n* − *i*) tokens, not from the same `(rule, position)` pair
being asked redundantly. pest compiles `(Infix ~ Primary)*` as one flat
iterative loop inside `DataExpr`'s own matcher, not as a chain of separately
memoizable recursive calls — so "`DataExpr`'s reach from *i*" and "from
*i*+1" share no memoized substructure to reuse. Getting O(*n*) out of
memoization here needs the grammar restructured to be explicitly
right-recursive (`Chain = Primary ~ (Infix ~ Primary ~ Chain)?`, so each
position's "rest of the chain" is its own rule pest can memoize) — pest's
own memoization, if it had any, wouldn't help the *current* grammar shape on
its own.

## The fix: two markers, not a table

A precomputed *reachability table* ("can `ProcExprIfPrefix` succeed starting
here, in O(1)?") only fixes the first cause — it says nothing about what
happens after a genuine condition is found, which is exactly where the second
one lives. `condition_marker.rs`'s `mark_process_conditions` fixes both with
one linear left-to-right scan over the source text, run once in Rust before
handing text to pest at all:

- It finds every position that is genuinely the start of a condition (using
  the same conservative, "guess wrong ⇒ scan stops, never guess a different
  AST" token-shape reasoning `disambiguation.md` uses elsewhere) and inserts
  a Private-Use-Area codepoint, `CONDITION_MARKER` (`'\u{E000}'`), there.
  `mcrl2_grammar.pest` requires this marker before `ProcExprIfPrefix`/
  `ProcExprIfThen` ever attempt `DataExpr`, so a non-condition position now
  fails in O(1) instead of walking the chain.
- For every condition it finds, a small stack (`pending_ifs`) implements the
  standard nearest-enclosing-if rule: on `->`, push; on `<>`, pop and mark the
  popped condition's arrow position with a second codepoint, `ELSE_MARKER`
  (`'\u{E001}'`). The grammar requires this marker before ever attempting the
  `(ProcExprNoIf ~ "<>")?` tail, so a bare condition's tail-check is also
  O(1) — it never touches `ProcExprNoIf` at all unless the scan already
  proved a matching `<>` exists.

Both codepoints are Private-Use-Area, ASCII-hostile mCRL2 source can never
contain, and are silent (`_{ }`) in the grammar, so they never show up as
extra AST children. Neither marker needs to be exhaustively correct: getting
one wrong can only make a doomed attempt fail slightly differently — never
produce a *silently different* AST, since the marker's absence just forces a
hard parse error. `UntypedProcessSpecification::parse` tries the marked text
first and falls back to parsing the *original*, unmarked text on any failure,
so a scanner gap costs the speedup for that one input, never correctness.

The marker insertion shifts every later byte offset by `CONDITION_MARKER_LEN`
per marker, which would otherwise corrupt every span downstream. Rather than
have every span-computing call site in `merc_syntax` know about the shift,
[`with_offset_corrections`](https://mercorg.github.io/merc/merc_utilities/span/fn.with_offset_corrections.html)
(`merc_utilities`) installs a thread-local correction for the duration of the
marked parse; `Span`'s `From<pest::Span>` conversion applies it
transparently, so every ordinary `span.into()` call already gets the
corrected offset with no changes anywhere else. See also
[Source Maps & Imports](source_map.md) for the other place this crate
threads offsets through a parse without touching every call site.

Result: `MLV.mcrl2` and `garage-ver.mcrl2` — previously non-terminating —
now parse in ~40 ms and ~70 ms respectively (debug build; ~4 ms / ~7 ms
release). Every one of the 528 `merc_syntax` tests that passed before this
fix still passes byte-for-byte, and the suite now totals 531 with the two
example specs and one regression test the fix re-enables.

## A dead end: merging `ProcExprNoIf` into `ProcExpr`

Before landing on the marker scan, we considered a structural alternative:
delete `ProcExprNoIf` (in the current grammar it's already identical to
`ProcExpr` — same primary/infix set — existing only so `ProcExprIfThen`'s
children come back as a distinguishable pest node), make `->` a bare prefix
with no embedded tail, and make `<>` a *flat infix token* sitting in
`ProcExprInfix` next to `+`/`.`/`||`. Grammar-level parsing then becomes one
linear pass — no nested optional sub-rule to recurse through — and attaching
`<>` to the right enclosing `->` becomes the Pratt parser's ordinary
linear-time precedence climbing instead of PEG backtracking. That would kill
the second cause by construction, no scanning needed.

It doesn't work, for a reason only visible by checking against the real
mCRL2 grammar and its actual parser instead of guessing. mCRL2's own grammar
*does* have a `ProcExprNoIf`/`ProcExpr` split — it's the textbook "matched
statement" non-terminal used to resolve dangling-else, not a PEG artifact —
and merc's operator-precedence table (`ProcExprInfix`) already matches it
level for level: Choice = 1, Sum/Dist = 2, Parallel/LeftMerge = 3, If = 4,
Until = 5, Seq = 6, At = 7, Sync = 8 (compare
[the mCRL2 process expression grammar](https://mcrl2.org/web/user_manual/language_reference/process.html)
and [mCRL2org/mCRL2#917](https://github.com/mCRL2org/mCRL2/issues/917), which
quotes the actual precedence-annotated grammar and a rejected — `wontfix` —
proposal to merge the two rules, for exactly the reason below).

A flat, statically-precedenced `<>` infix token can't reproduce what real
mCRL2 actually does here, because *whether the `then` branch widens across
`+` depends on whether a matching `<>` exists later in the input* — an
inherently lookahead-dependent decision no static precedence value can
express. Verified directly against `mcrl22lps` (`--no-constelm` to stop
constant-propagation from collapsing the boolean parameters away before the
guards can be compared):

```
proc P(x, y: Bool) = x -> y -> a <> b;
init P(true, true);
```

parses byte-for-byte identically — same guard on `b`, `x && !y` — to the
explicitly-parenthesized `x -> (y -> a <> b)`, *not* `x -> (y -> a) <> b`.
Extending to two nested `<>`s pins it down further:

```
proc P(x, y: Bool) = x -> y -> a <> b <> e;
```

parses identically to `x -> (y -> a <> b) <> e`: the *first* `<>` closes the
*most recently opened* condition (`y`'s), the second closes `x`'s — standard
nearest-enclosing-if, confirmed on the actual `mcrl22lps` binary, not
assumed from the grammar text. `merc_syntax` (with the marker fix) parses
both examples identically to `mcrl22lps`.

This also settles why `ProcExprNoIf` can't simply be tightened to *forbid*
bare nested conditions (as real mCRL2's own documentation literally claims it
does — "no if-then or if-then-else productions are allowed" — which does
not match what the shipped `mcrl22lps` 202607.0 binary we tested against
actually accepts): the second example needs `ProcExprNoIf`, when parsing
`x`'s `then` branch, to recognize `y -> a <> b` as a nested condition-with-
its-own-`<>` in order to find where `x`'s own `then` branch ends. Removing
that recursion would reject input the real toolset accepts, not just clean
up merc's grammar — a conformance regression, not a fix. The marker-based
scan handles exactly this case already: `pending_ifs`'s stack discipline is
scoped per `scan_expr_region` call, so a `<>` inside a nested `(...)` can
only close an `if` inside those same parens, and a bare nested condition
resolves to the *innermost* still-open one, matching `mcrl22lps` by
construction rather than by coincidence.

See also [Precedence: Pest (merc) vs. dparser (mCRL2)](precedence.md), which
verifies a *different* class of parser disagreement (a genuine precedence
divergence, not a performance issue) the same way — against the actual
`mcrl22lps`/dparser behavior rather than the documented grammar, which this
page's findings show can itself be stale or imprecise.
