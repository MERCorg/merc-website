```math_preamble
\usepackage{stmaryrd}
```
# Machine numbers

mCRL2's numeric sorts `Pos`, `Nat`, `Int` and `Real` can be built on top of
either of two representations of natural numbers. Both represent the same values
and satisfy the same equations; they differ in how a number is built from smaller
pieces, and in what that choice costs. This page defines the two encodings
(Definitions 1 and 2) and states what is proved about the second (Theorem 1).
A data specification is type checked for one of them, selected by
[`NumberEncoding`](https://mercorg.github.io/merc/merc_typecheck/).

## Binary encoding

The default representation is the one given in the mCRL2 language definition
itself (Appendix B of the mCRL2 manual): a *recursive binary* encoding. A
`Pos` (a positive natural number) is built from two constructors,

```
@c1                      = 1
@cDub(b : Bool, p : Pos) = 2p + b
```

so every positive number is a chain of bits, least-significant bit closest to
`@c1`, exactly like ordinary binary notation read outward-in.

<a id="def-binary-encoding"></a>**Definition 1 (binary encoding).** In the *binary encoding*, the values of `Pos`
are the terms built from `@c1` and `@cDub`, with $\llbracket \mathtt{@c1}
\rrbracket = 1$ and $\llbracket \mathtt{@cDub}(b, p) \rrbracket =
2\llbracket p \rrbracket + \llbracket b \rrbracket$. `Nat` adds a
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
directly rather than derived one bit at a time from equations.

<a id="def-machine-word-encoding"></a>**Definition 2 (machine-word encoding).** In the *machine-word encoding*, the
normal forms of `Pos` are digit chains: `@most_significant_digit(w)` for a
non-zero 64-bit word $w$, and `@concat_digit(p, w)`, with
$\llbracket \mathtt{@most\_significant\_digit}(w) \rrbracket = w$ and
$\llbracket \mathtt{@concat\_digit}(p, w) \rrbracket = 2^{64}\llbracket p
\rrbracket + w$. So a `Pos` is a most-significant word followed by zero or more
words, each concatenated on the less-significant side:

$$
\underbrace{w_0}_{\text{most significant}} \; w_1 \; \cdots \; w_k
\;=\; \sum_{i=0}^{k} w_i \cdot 2^{64(k-i)}
$$

which is exactly ordinary positional notation, but in base $2^{64}$ instead
of base $2$. The digit functions are mappings, not constructors: the constructors
of `Pos` are `@c1` and `@succ_pos`, so that a number built the generic way, with
successors, still has a sort to belong to until it is rewritten to a digit chain
(see [The set automaton](set-automaton.md#example-on-machine-word-pos) for a
consequence). `Nat`, `Int` and `Real` are built from this the same way they
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

<a id="thm-machine-word-operations"></a>**Theorem 1 (machine-word operations).** For words of any width $n$ (merc uses
$n = 64$; some operations need $n \ge 2$), the operations of the machine-word encoding of `Pos`, `Nat`, `Int` and `Real`
(constants, successor and predecessor, comparisons, minimum and maximum,
addition, subtraction, multiplication, division, remainder, exponentiation, and
rounding of reals), applied to canonical digit chains, compute the corresponding
operation on $\mathbb{N}$, $\mathbb{Z}$ or $\mathbb{Q}$; and so do the
operations on single words. The same holds for the binary encoding.

Theorem 1 is proved in Lean, without `sorry`, in the verified-machine-numbers
formalisation, which is not public: one statement per operation, for example
`MPos.add_toNat` and `MPos.lt_toNat`, in `MachineNumbers/Generic` for the
machine-word encoding and `MachineNumbers/Binary` for the binary one, with the
human-vetted statements in `Challenges/`. A digit chain is *canonical* if its
most significant word is non-zero.

### Performance

The main usecase for the machine numbers is the efficiency of computing with
numbers. Concretely, the gap is large enough to matter well before numbers get
large: the bundled end-to-end tests record `sqrt(65535) * sqrt(65535) <= 65535`
taking roughly 20 s to rewrite under the binary encoding against roughly 0.4 s
under the machine-word one.
