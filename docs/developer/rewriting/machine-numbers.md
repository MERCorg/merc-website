# Machine Numbers

mCRL2's numeric sorts `Pos`, `Nat`, `Int` and `Real` can be built on top of
either of two different representations of natural numbers. Both represent
the same values and satisfy the same equations — they differ only in how a
number is built up out of smaller pieces, and in what that choice costs.

## Binary encoding

The default representation is the one given in the mCRL2 language definition
itself (Appendix B of the mCRL2 manual): a *recursive binary* encoding. A
`Pos` (a positive natural number) is built from two constructors,

```
@c1                 = 1
@cDub(b : Bool, p : Pos) = 2p + b
```

so every positive number is a chain of bits, least-significant bit closest to
`@c1`, exactly like ordinary binary notation read outward-in. `Nat` adds a
constructor for zero, `Int` adds a sign, and `Real` pairs an `Int` numerator
with a `Pos` denominator — all built on the same bitwise representation of
magnitude. Arithmetic on this representation is defined the same way the
sorts themselves are: by rewrite rules that consume and produce these
constructors one bit at a time. Addition, for instance, is a recursive
equation over `@cDub`, propagating a carry bit exactly as long addition does
on paper.

The appeal of this encoding is that it needs nothing beyond the rewriting
system that already interprets the rest of an mCRL2 specification. Every
arithmetic fact — that $2+2=4$, that multiplication distributes over addition
— follows from the same small set of equations that define the sorts, so
trusting the arithmetic is no different from trusting any other rewrite rule
in the specification. The cost of that transparency is speed: representing an
$n$-bit number takes a chain of $n$ nested terms, and an operation such as
addition or multiplication walks that chain bit by bit, so its cost grows
with the number of *bits*, not the number of machine words. Two numbers a few
hundred bits wide already take a rewriting engine a visibly long time to
multiply or take the square root of, purely from the bookkeeping of building
and matching all those intermediate terms.

## Machine-word encoding

The second representation trades that transparency for speed by mirroring
how a CPU represents numbers: as a chain of native 64-bit *machine words*
instead of a chain of bits, with the arithmetic on those words computed
directly rather than derived one bit at a time from equations. The
constructors change accordingly — a `Pos` is a most-significant word,
followed by zero or more additional words each concatenated on the
less-significant side:

$$
\underbrace{w_0}_{\text{most significant}} \; w_1 \; \cdots \; w_k
\;=\; \sum_{i=0}^{k} w_i \cdot 2^{64(k-i)}
$$

which is exactly ordinary positional notation, but in base $2^{64}$ instead
of base $2$. `Nat`, `Int` and `Real` are built from this the same way they
are built from the binary encoding: a `Nat` adds a representation of zero, an
`Int` adds a sign, a `Real` pairs a numerator and denominator.

The operations on the individual 64-bit words — addition, multiplication,
comparison, division, square root, together with the carry/overflow flags
needed to detect when a result no longer fits in one word — are not given by
rewrite rules at all. They are implemented directly, the same way a CPU or a
software bignum library would implement them, and are simply asserted by the
specification to compute the intended arithmetic. Multiplying two words, for
example, produces a result that no longer fits in a single word, so it is
computed in a wider representation and split back into a (low word, high
word) pair — the machine-word analogue of "carry the 1". Because these word
operations run as ordinary code rather than being unfolded step by step by
the rewriter, an $n$-bit number costs only $O(n/64)$ words, and each
operation on a word is one native machine instruction rather than a sequence
of rewrite steps — the same asymptotic quantity, bits, is now amortized 64 at
a time.

## Why have both

The two encodings are answers to different questions about the same
arithmetic. The binary encoding answers "is this the number the
specification says it is?" as directly as possible: every step is a rewrite
rule, so nothing about the arithmetic needs to be trusted beyond the
rewriting system itself. The machine-word encoding answers "can this be
computed fast enough to be useful?": by delegating the arithmetic on
individual words to native code, it turns a computation that costs one
rewrite step *per bit* into one that costs a small, fixed number of native
operations *per word*, which is the difference between arithmetic that scales
to the sizes model checking and reachability analysis actually produce and
arithmetic that does not. The price of that speed is that the native word
operations are no longer verified by the same means as the rest of the
specification — each one has to be shown, separately, to compute exactly the
infinite-precision operation its type and surrounding equations assume it
performs, since a bug there is no longer a bug a proof about the rewrite
rules would catch.

Concretely, the gap is large enough to matter well before numbers get large:
the bundled end-to-end tests record `sqrt(65535) * sqrt(65535) <= 65535`
taking roughly 20 s to rewrite under the binary encoding against roughly
0.4 s under the machine-word one. Both encodings remain available —
`merc` exposes the choice as
[`NumberEncoding`](https://github.com/MERCorg/merc/blob/main/crates/typecheck/src/number_encoding.rs)
(`Binary` or `MachineWord`) — because the right trade-off depends on what a
specification is being used for: the binary encoding when trusting the
arithmetic to be exactly what the equations say matters most, the
machine-word encoding when the specification's numbers are large or its
arithmetic runs often enough that speed dominates.
