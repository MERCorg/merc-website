# Rewriting benchmarks

Measurements of the rewriters in
[`merc_sabre`](https://mercorg.github.io/merc/merc_sabre/index.html) and of the
data enumeration in
[`merc_enumerate`](https://mercorg.github.io/merc/merc_enumerate/index.html). The
designs that they evaluate are described under
[Rewriting](../rewriting/rewriters/conditional-rewriting.md).

## Rewriter comparison

The tables compare the [innermost](../rewriting/rewriters/innermost.md) and
[jitty](../rewriting/rewriters/jitty.md) rewriters of `merc` with mCRL2, under the
binary and the [machine-word](../rewriting/data/machine-numbers.md) encoding
of numbers.

They give criterion means of the benchmarks of `merc_sabre` and
`merc_enumerate`, each benchmark in its own process and built with one codegen
unit and fat link-time optimisation, since both the state of the term pool
left by earlier benchmarks and the code layout of the term pool otherwise
change timings by 10% to 40%. The mCRL2 times are per evaluation in
`mcrl2i -rjitty`, under the same encodings.

**Number encodings** (`benchmark_number_encoding`):

| goal | innermost binary | jitty binary | mCRL2 binary | innermost word | jitty word | mCRL2 word |
|---|---:|---:|---:|---:|---:|---:|
| fib | 15 ms | 18 ms | 25 ms | 11 ms | 12 ms | 19 ms |
| sum | 20 ms | 23 ms | 15 ms | 8.7 ms | 9.8 ms | 7.5 ms |
| count | 1.3 s | 37 ms | 29 ms | 8.3 ms | 9.3 ms | 9.2 ms |
| sqrt | 3.7 ms | 0.23 ms | 0.43 ms | 26 µs | 27 µs | 0.27 ms |
| sort | 2.1 s | 394 ms | 515 ms | 70 ms | 88 ms | 92 ms |
| compare | 104 ms | 25 µs | | 18 µs | 18 µs | |
| exp | > 30 s¹ | 35 ms | 52 ms | no termination | 0.17 ms | 0.28 ms |

The mCRL2 times leave out the fixed cost of a query, about 2.4 ms, which is
the time of a single comparison, so the comparisons are too fast to measure
there.

¹ Not a benchmark, since it takes too long.

**Quantifier goals** (`benchmarks_enumerate`), which the rewriters decide with
[data enumeration](../rewriting/data/enumeration.md). The mCRL2 times include
its fixed cost of up to 0.4 ms per query.

| goal | innermost binary | jitty binary | mCRL2 binary | innermost word | jitty word | mCRL2 word |
|---|---:|---:|---:|---:|---:|---:|
| sqrt | 0.53 ms | 0.57 ms | 1.0 ms | 18 ms | 18 ms | 27 ms |
| parity | 3.2 ms | 3.2 ms | 4.4 ms | 4.7 ms | 4.6 ms | 8.4 ms |
| one_point | 0.34 ms | 0.22 ms | 0.43 ms | 73 ms | 25 ms | 15 ms |
| nested | 0.80 ms | 0.87 ms | 1.5 ms | 2.2 ms | 2.3 ms | 2.4 ms |
| deep_nested | 8.0 ms | 5.5 ms | 5.6 ms | 6.8 ms | 5.7 ms | 6.5 ms |
| siblings | 1.1 ms | 1.4 ms | 2.0 ms | 3.1 ms | 3.1 ms | 3.9 ms |
| sum_squares | 0.27 ms | 0.34 ms | 1.3 ms | 42 ms | 44 ms | 66 ms |
| xor_assoc | 2.2 ms | 3.2 ms | 3.7 ms | 2.2 ms | 3.3 ms | 3.6 ms |
| pigeonhole | 0.40 ms | 0.34 ms | 1.8 ms | 0.43 ms | 0.36 ms | 1.8 ms |

**REC** (`benchmark_sabre`): the REC specifications are strict, so both
rewriters apply the same rules equally often.

| specification | innermost | jitty |
|---|---:|---:|
| fibfree | 1.5 ms | 2.0 ms |
| benchexpr20 | 2.4 s | 2.8 s |
| evalexpr | 2.9 s | 3.4 s |
| sieve1000 | 1.2 s | 2.0 s |
| tak36 | 1.1 s | 1.7 s |

Where both rewriters do the same work, the jitty rewriter is up to 70% slower, the
most on `sieve1000`, `tak36` and `xor_assoc`;
[Just-in-time rewriting, Performance](../rewriting/rewriters/jitty.md#performance)
explains why.

The enumeration of the quantifier goals is faster than in mCRL2 on all goals
but `one_point` under machine words. Rewriting itself is faster than mCRL2 on
most goals as well, but slower on `sum` and `count`.

## Term pool access

Taking every step in an access to the term pool of its own, rather than
[many steps in a single access](../rewriting/rewriters/jitty.md#one-machine-for-both-rewriters),
makes both rewriters 15% to 40% slower.

## Matching without building the redex

Constructing every redex and discarding it again, rather than
[matching it where it lies](../rewriting/rewriters/innermost.md#matching-without-building-the-redex),
makes the REC benchmarks of the innermost rewriter 14% to 130% slower.

## Machine numbers

The end-to-end tests of `merc_sabre` record
`sqrt(65535) * sqrt(65535) <= 65535` taking roughly 20 s to rewrite under the
binary encoding against roughly 0.4 s under the
[machine-word encoding](../rewriting/data/machine-numbers.md#performance).

## Condition caching

Rewrite steps of the
[`InnermostRewriter`](https://mercorg.github.io/merc/merc_sabre/struct.InnermostRewriter.html)
for the [condition cache](../rewriting/rewriters/condition-caching.md).

On the EVAL terms of `evalexpr.rec`:

| cache | rewrite steps |
|---|---:|
| static only | 19,698,985 |
| dynamic | 8,265,493 |

On a synthetic `slow(x)` specification of the shape of the
[limitation](../rewriting/rewriters/condition-caching.md#limitation), where `slow`
takes `n` steps to normalise:

| conditions | rewrite steps | `slow(x)` computed |
|---|---:|---|
| `not(slow(x)) = true` alongside `slow(x) = true` | 403 | twice |
| both conditions written as `slow(x)` in full | 201 | once, with one cache hit |

## One-point rule

Rewrite calls of the `InnermostRewriter`, one per expanded branch, to find the
witness of the goal in
[Data enumeration, Gap: a one-point conjunct exposed during the search](../rewriting/data/enumeration.md#gap-a-one-point-conjunct-exposed-during-the-search):

| goal | rewrite calls |
|---|---:|
| the guard, searched as written | 58 |
| the same guard with `n` already fixed to `0`, so that `m == 50` is a one-point conjunct from the start | 1 |

The second row is what a dynamic rule, re-applied after every expansion, would
achieve on this goal.

## Nested quantifiers

For the goal `forall x: Nat . x < 30 => exists y: Nat . y < 30 && x + y == 2`,
[replacing the inner quantifier by the combination of its leaves](../rewriting/data/quantifiers.md#nested-quantifiers)
makes rewriting almost four times faster than keeping the inner quantifier.
