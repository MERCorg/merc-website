# Machine Numbers

mCRL2's numeric sorts `Pos`, `Nat`, `Int` and `Real` are formally specified as
*recursive binary* numbers (Appendix B of the mCRL2 manual): a `Pos` is a chain
of bits, `@c1` or `@cDub(b, p)` denoting $2p+b$, built and consumed one bit at a
time by ordinary rewrite rules. That specification is easy to trust — every
rule is a small equation you can read — but it is also slow: adding two
$n$-bit numbers this way costs $O(n)$ rewrite steps, and each of those steps
builds a term rather than issuing a machine instruction. The bundled
end-to-end tests record the gap on one concrete case: evaluating
`sqrt(65535) * sqrt(65535) <= 65535` takes roughly 20 s under the binary
encoding against roughly 0.4 s under the machine-word one.

mCRL2 (and `merc`) also offer a second representation that trades some of that
transparency for speed: numbers as chains of native 64-bit *machine words*,
with the arithmetic on those words computed directly by code instead of
rewrite rules — the same way a CPU would do it. `merc` calls the choice
[`NumberEncoding`](https://github.com/MERCorg/merc/blob/main/crates/typecheck/src/number_encoding.rs)
(`Binary`, the default, or `MachineWord`), threaded through
`DataSpecification::from_untyped_with`. This page describes the `MachineWord`
representation: how numbers are built from 64-bit digits, what operations are
provided on those digits, and — since these operations are implemented
directly rather than derived from equations — why each one can be trusted to
compute exactly what its specification says it should.

!!! info "Where this lives"
    The digit operations themselves are plain functions on `u64` in
    [`merc_number::machine_word`](https://github.com/MERCorg/merc/blob/main/crates/number/src/machine_word.rs).
    Dispatching a rewrite-time application to one of them is
    [`MachineWordOp`](https://github.com/MERCorg/merc/blob/main/crates/data/src/machine_word_evaluation.rs)
    in `merc_data`. Both are close Rust ports of mCRL2's
    [`detail/machine_word.h`](https://github.com/mCRL2org/mCRL2/blob/master/libraries/data/include/mcrl2/data/detail/machine_word.h)
    and [`machine_word.cpp`](https://github.com/mCRL2org/mCRL2/blob/master/libraries/data/source/machine_word.cpp).

## The `@word` sort

`@word` is a system sort whose values are the natural numbers below $2^{64}$ —
a single machine word. Its arithmetic is not that of $\mathbb{N}$: `@add_word`,
`@times_word` and their relatives wrap, so on those operations `@word` behaves
as $\mathbb{Z}/2^{64}\mathbb{Z}$, the integers modulo $2^{64}$, while `@less`,
`@div_word` and `@sqrt_word` read the same word as an ordinary natural number.

Unlike `Pos` or `Nat`, none of these operations is given a rewrite rule. In
mCRL2's code-generator input,
[`machine_word.spec`](https://github.com/mCRL2org/mCRL2/blob/master/scripts/code_generation/data_types/machine_word.spec),
every one of them carries the annotation `internal defined_by_code`: the
specification fixes the operation's name and type, not a rewrite rule for it —
the rule is "run the native code".
[`machine_word.mcrl2`](https://github.com/MERCorg/merc/blob/main/crates/syntax/spec/machine_word.mcrl2),
the copy `merc` bundles, is the same declaration list with the code-generation
annotations stripped, and the only equations it carries redirect the generic
operators onto the native comparisons:

```
eqn  (w1 == w2) = @equal(w1, w2);
     (w1 < w2)  = @less(w1, w2);
     (w1 <= w2) = @less_equal(w1, w2);
```

Only `@zero_word` and `@succ_word` are declared as constructors of `@word`;
everything else is a mapping. The operations fall into a few groups:

| Group | Operations |
|---|---|
| Constants | `@zero_word` … `@four_word`, `@max_word` |
| Word predicates | `@equals_zero_word`, `@not_equals_zero_word`, `@equals_one_word`, `@equals_max_word`, `@rightmost_bit` |
| Comparisons | `@equal`, `@not_equal`, `@less`, `@less_equal`, `@greater`, `@greater_equal` |
| Carry flags | `@add_overflow_word`, `@add_with_carry_overflow_word` |
| Wrapping arithmetic | `@succ_word`, `@pred_word`, `@add_word`, `@add_with_carry_word`, `@times_word`, `@times_with_carry_word`, `@minus_word` |
| Exact word arithmetic | `@monus_word`, `@div_word`, `@mod_word`, `@sqrt_word` |
| Multi-word (base $2^{64}$) | `@times_overflow_word`, `@times_with_carry_overflow_word`, `@div_doubleword`, `@mod_doubleword`, `@div_double_doubleword`, `@div_triple_doubleword`, `@sqrt_doubleword`, `@sqrt_tripleword(_overflow)`, `@sqrt_quadrupleword(_overflow)` |
| Bit shift | `@shift_right` |

In `merc`, each of these is a small function over plain `u64` (or `u128`/
`BigUint` for the multi-word ones, see below), living in a crate that is
`#![forbid(unsafe_code)]` as a whole — there is no unsafe bit-twiddling
anywhere in this layer, only the arithmetic itself has to be right.

!!! note "One function with no operation"
    `machine_word.rs` also defines `mod_double_doubleword`, mirroring a C++
    function of the same name. Neither mCRL2's specification nor
    `machine_word.mcrl2` declares a matching `@`-operation, so it has no
    `MachineWordOp` variant and no rewrite can reach it; it exists only to keep
    the port complete.

## Digit chains: representing `Pos`, `Nat`, `Int` and `Real`

A single `@word` is only ever one digit. Larger numbers are built the same way
the binary encoding builds bit chains, but in base $2^{64}$ instead of base
$2$: [`pos64.mcrl2`](https://github.com/MERCorg/merc/blob/main/crates/syntax/spec/pos64.mcrl2)
declares

```
map  @most_significant_digit: @word -> Pos;
     @concat_digit: Pos # @word -> Pos;
```

as *mappings*, not constructors — `Pos`'s constructors remain `@c1` and
`@succ_pos`, which the equations rewrite into digit form immediately, starting
with `@c1 = @most_significant_digit(@one_word)`. Their intended reading is
positional: `@concat_digit(p, w)` denotes $2^{64}p + w$, a convention
[`nat64.mcrl2`](https://github.com/MERCorg/merc/blob/main/crates/syntax/spec/nat64.mcrl2)
spells out in a comment on its own overload. So a `Pos` is
`@most_significant_digit(w_0)` for a one-digit number, and each
further, less-significant digit wraps the chain one more time — a three-digit
number is `@concat_digit(@concat_digit(@most_significant_digit(w_0), w_1), w_2)`,
denoting $w_0 \cdot 2^{128} + w_1 \cdot 2^{64} + w_2$ — most-significant digit
first, exactly like ordinary positional notation.
`Nat` has its own leading mapping `@most_significant_digitNat` and its own
`@concat_digit` overload of type `Nat # @word -> Nat` (so it can represent `0`,
which `Pos` cannot), with its constructors `@c0` and `@succ_nat` likewise
rewritten into digit form (`@c0 = @most_significant_digitNat(@zero_word)`).
`Int` is `@cInt(n : Nat)` or `@cNeg(p : Pos)` and `Real` is
`@cReal(numerator : Int, denominator : Pos)` in both encodings, since sign and
fraction structure don't depend on how the underlying `Nat`/`Pos` magnitude is
represented.

`merc`'s `MachineNumber` data expression
([`crates/data/src/data_expression.rs`](https://github.com/MERCorg/merc/blob/main/crates/data/src/data_expression.rs))
is exactly one such digit — a `u64` whose bit pattern is stored in an
`ATermInt` leaf — never a whole `Pos`/`Nat` by itself. The lowering of a
decimal literal
([`digit_chain_literal`](https://github.com/MERCorg/merc/blob/main/crates/typecheck/src/ir/mcrl2_lowering.rs))
nests `@most_significant_digit`/`@concat_digit` applications around one
`MachineNumber` leaf per digit, and the rewriter's own normal forms look the
same:

```
2 + 2                    ⇒  @most_significant_digitNat(4)
18446744073709551621     ⇒  @concat_digit(@most_significant_digitNat(1), 5)
```

the second being $1 \cdot 2^{64} + 5$, the first value that needs two digits.

## Why the native `@word` operations are correct

Because these operations bypass equations entirely, their correctness cannot
be checked the way an ordinary defined function's can — by reading the rule
and matching it against the sort's intended meaning. Instead, each native
function has to be an exact implementation of the arithmetic its type and
surrounding equations assume it performs. The argument for each group of
operations below is the same shape: state precisely which infinite-precision
operation the function stands in for, then show the `u64`/`u128`/`BigUint`
code computes exactly that.

### Wrapping *is* the specification

For the operations in the wrapping row above — `@succ_word`, `@pred_word`,
`@add_word`, `@add_with_carry_word`, `@times_word`, `@times_with_carry_word`
and `@minus_word` — reduction modulo $2^{64}$ is the intended semantics rather
than an accident of the machine. This is implemented with Rust's explicit
`wrapping_*` methods:

```rust
pub fn add_word(n1: u64, n2: u64) -> u64 {
    n1.wrapping_add(n2)
}
```

This is not a stylistic choice — plain `n1 + n2` is the *wrong* function here.
On `u64`, Rust's `+` panics on overflow in debug builds and silently wraps in
release, so its behaviour would depend on the build profile even though the
mathematical operation being modelled (`Z/2^64Z` addition) does not. mCRL2's
C++ backend gets the same modular semantics "for free" — the C++ standard
defines unsigned integer arithmetic as wraparound — but Rust has no such
default for `+`, hence the explicit `wrapping_*` call at every one of these
sites.

The remaining word-valued operations do not wrap, and are not written as if
they did. `@monus_word` is monus, $\max(0, n_1-n_2)$ rather than modular
subtraction, implemented with `saturating_sub`, which is precisely that for
unsigned integers by definition. `@div_word` and `@mod_word` are plain `/` and
`%` — exact Euclidean division for any non-zero divisor, and in the bundled
equations the divisor is always the single digit of a one-digit `Pos`, which
cannot be zero. (A violated precondition would at least be loud: Rust panics on
a zero divisor where the C++ has undefined behaviour.)

### Overflow flags must match the carry the digit chain relies on

`Pos`'s addition equation for two one-digit numbers is

```
(@most_significant_digit(w1) + @most_significant_digit(w2)) =
   if(@add_overflow_word(w1, w2),
      @concat_digit(@most_significant_digit(@one_word), @add_word(w1, w2)),
      @most_significant_digit(@add_word(w1, w2)));
```

— the digit chain grows a new leading digit *exactly when* `@add_overflow_word`
says so. If that flag were ever wrong, the result would be silently truncated
(a missed carry) or padded with a spurious extra digit (a false carry), and
every equation built on top would inherit the error. `@add_overflow_word` is

```rust
pub fn add_overflow_word(n1: u64, n2: u64) -> bool {
    n1.checked_add(n2).is_none()
}
```

`checked_add` returns `None` exactly when the true, unbounded-precision sum
$n_1+n_2$ is $\geq 2^{64}$ — precisely the condition under which
`@add_word`'s wrapped result no longer equals that true sum. So the pair
(`add_word`, `add_overflow_word`) is a complete decomposition of the exact sum
into a (digit, carry) pair, the same invariant `@concat_digit` needs to
interpret the result correctly. For this operation it is also exactly what
mCRL2's C++ implementation computes with the classic wraparound trick
`n1 + n2 < n1` instead of a checked add: for $n_1, n_2 < 2^{64}$, the wrapped
sum $s = (n_1+n_2) \bmod 2^{64}$ satisfies $s < n_1$ if and only if the true
sum overflowed — if it didn't, $s = n_1+n_2 \geq n_1$; if it did,
$s = n_1+n_2-2^{64}$, so $s - n_1 = n_2 - 2^{64} < 0$. Two different-looking
computations, same predicate.

`@add_with_carry_word` and `@add_with_carry_overflow_word` fold an extra `+1`
into the same pattern, for the case where a lower digit has already produced a
carry to propagate — but there the two implementations are *not*
interchangeable. `merc` computes

```rust
pub fn add_with_carry_overflow_word(n1: u64, n2: u64) -> bool {
    n1.checked_add(n2).and_then(|s| s.checked_add(1)).is_none()
}
```

which is true exactly when $n_1+n_2+1 \geq 2^{64}$, whereas the C++ test
`n1 + n2 + 1 < n1` misses the case $n_2 = 2^{64}-1$: the true sum is then
$n_1 + 2^{64}$, which always overflows, yet it wraps back to exactly $n_1$, so
the strict `<` is false. Compiling the C++ expression confirms the divergence —
at $n_1 = 0, n_2 = 2^{64}-1$ it reports no overflow where `merc` reports one.
`merc`'s is the version the digit-chain equation needs: the chain must grow a
digit whenever the exact sum leaves the word.

### Wide products, quotients and roots reconstruct the exact value

The 128-bit-and-wider operations follow the same principle: compute the exact
value in a *wider* representation, then split it into words the way
`@concat_digit` expects — most significant first, base $2^{64}$ — and truncate
where the operation's contract says to. For example:

```rust
pub fn times_overflow_word(n1: u64, n2: u64) -> u64 {
    ((n1 as u128 * n2 as u128) >> WORD_BITS) as u64
}
```

Since both factors are `< 2^64`, their product is `< 2^128`, so it fits in a
`u128` without loss; `times_word` (the low 64 bits) and `times_overflow_word`
(the high 64 bits, shown here) between them satisfy
`times_overflow_word(a,b) * 2^64 + times_word(a,b) == a as u128 * b as u128`
exactly — no rounding is possible because nothing was ever truncated before
the split. `@div_doubleword`/`@mod_doubleword` work one level up: they build
the two-digit numerator as a `u128`, divide exactly, and then narrow the result
to a word with `as u64`. That narrowing is lossless only while the quotient
still fits in one word — that is, while the numerator's high digit is below the
divisor. Nothing in the function checks this, and neither the specification nor
the C++ states it, so it is a precondition on the calling equations; `merc`'s
randomised tests construct their inputs to respect it.

Beyond 128 bits (`@div_triple_doubleword`, the triple/quadruple-word square
roots) there is no native Rust integer type wide enough, so `merc` falls back
to [`num::BigUint`](https://docs.rs/num/), arbitrary-precision arithmetic.
mCRL2's C++ backend makes the same split for the same reason, one step earlier
in the type system: `boost::multiprecision::uint128_t` where Rust has a native
`u128`, and `uint256_t` at exactly the operations where `merc` reaches for
`BigUint`. `BigUint` is assembled from words with the same
most-significant-digit-first, base $2^{64}$ convention the digit chain itself
uses (`big_from_digits`/`truncate_u64` in `machine_word.rs`), so composing the
wide value, computing on it, and truncating the result to the low word all
line up with what the calling equation expects.

### Square roots are correct by their defining property

`@sqrt_word` and its multi-word variants compute the *floor* of the integer
square root, $r = \lfloor\sqrt{n}\rfloor$. This value is characterised
uniquely by $r^2 \leq n < (r+1)^2$, so any computation that produces a value
satisfying this inequality is correct by definition, regardless of the
algorithm used internally. `merc` uses `num`'s `Roots::sqrt` for both `u64` and
`BigUint`, an exact integer root, so the property holds by construction rather
than by an argument about rounding — which is worth insisting on, because the
C++ `sqrt_word` instead evaluates the floating-point `sqrt` on the word and
truncates. A `double` has a 53-bit significand, not enough to separate every
64-bit input, and at the top of the range it rounds the wrong way: the C++
`sqrt_word(@max_word)` returns $2^{32}$, whose square $2^{64}$ exceeds
$2^{64}-1$, where `merc` returns the correct $2^{32}-1$. (The wider C++
variants call boost's integer `sqrt` on `uint128_t`/`uint256_t` and are not
affected.) `merc`'s own tests check the defining property directly — not merely
"matches some other implementation" — for the single-, double-, triple- and
quadruple-word variants.

## Verification: cross-checking against an independent bignum

Reading the code is only half the argument; `machine_word.rs` also backs it
with randomised, property-based tests (`merc_utilities::random_test`, 10,000
iterations for the arithmetic and division identities and 5,000 for the
square-root bounds) that check every operation against the *same* computation
performed on `num::BigUint` — a general-purpose arbitrary-precision library
with no relation to the hand-written word code, so agreement is not circular.
The identities checked include, among others:

- `add_word`/`add_with_carry_word` reconstruct `(a + b) mod base` and
  `add_overflow_word` agrees with `a + b >= base`, for the binary big-integer
  `base = 2^64`;
- `times_word`/`times_overflow_word` reconstruct the exact product
  `overflow * base + low == a * b`, and the carry-fused variants the same with
  a third addend;
- `div_word`/`mod_word` satisfy the Euclidean identity
  `quotient * divisor + remainder == numerator` with
  `0 <= remainder < divisor`, as do `div_doubleword`/`mod_doubleword` on a
  two-digit numerator; the still wider divisions are compared against
  `BigUint`'s own quotient under the same truncation to a word;
- `sqrt_*` satisfy $r^2 \leq n < (r+1)^2$ and agree with `BigUint`'s own root.

This is what actually establishes correctness in practice: a structural
argument for *why* each function should be right, checked against thousands of
random cases through an independent implementation of the infinite-precision
arithmetic the sort denotes.

## What a machine-checked proof would look like

!!! note "Speculative"
    None of this has been done. `merc` has no Lean development, and the case
    for these operations today is the structural argument above plus the tests.
    What follows is a sketch of the obligation a formal proof would have to
    discharge, and of the pieces that already exist to build it from.

These operations are an unusually tractable target for formalisation: a few
dozen total functions on `u64`, no allocation, no state, no concurrency, each
one standing in for a single arithmetic identity. And the shape of the proof is
the standard one for a data refinement — a *representation function* plus a
family of commuting squares.

**The obligation.** Fix an abstraction map $\alpha$ from the concrete
representation to the value it denotes. For a single word, $\alpha_w$ is
`UInt64.toNat`, landing in `ℕ` — or in `ZMod (2^64)`, if one prefers to state
the wrapping operations as a ring homomorphism rather than as a `% 2^64`
identity. For a digit chain, $\alpha$ is the base-$2^{64}$ fold: $\alpha$ of a
one-digit chain is $\alpha_w$ of its digit, and $\alpha$ of
`@concat_digit(p, w)` is $2^{64}\alpha(p) + \alpha_w(w)$. The obligation for a
native operation $f$ standing in for an abstract $F$ is then the commuting
square $\alpha(f(x, y)) = F(\alpha(x), \alpha(y))$, modulo whatever truncation
that operation's contract permits. Two concrete instances:

- *Addition and its carry are one theorem, not two.* Writing $s$ for the exact
  sum $\alpha_w(n_1) + \alpha_w(n_2)$ taken in `ℕ`, the statement to prove is
  $s = c \cdot 2^{64} + d$, where $d$ is the word `add_word` returns and $c$ is
  $1$ or $0$ according to `add_overflow_word`. That single equation is exactly
  what the `Pos` addition equation consumes when it decides whether to grow a
  digit, so proving it discharges the carry argument made informally above.
- *The fold itself.* Justifying the chain means showing it is ordinary
  positional notation. Mathlib's `Nat.ofDigits` is the same fold modulo digit
  order — `Nat.digits`/`Nat.ofDigits` are little-endian, least significant
  first, whereas a chain is written most significant first — so a
  chain-to-`List` function composed with `List.reverse` should let
  `Nat.ofDigits_digits : Nat.ofDigits b (Nat.digits b n) = n` do the round-trip
  work instead of re-deriving it.

**What it would build on.** Lean core's `BitVec` is close to a direct model of
the single-word layer: `UInt64` is a structure wrapping a `BitVec 64`, and the
`toNat` lemmas are stated in exactly the wrapping form these functions need —
`BitVec.toNat_add : (x + y).toNat = (x.toNat + y.toNat) % 2^w`, and similarly
for multiplication and subtraction. Core also carries the overflow predicates
`BitVec.uaddOverflow`, `BitVec.usubOverflow` and `BitVec.umulOverflow` with
conditional lemmas along the lines of `BitVec.toNat_add_of_not_uaddOverflow`
that drop the modulus when no overflow occurs — the `add_word` /
`add_overflow_word` pairing, already spelled out. `Nat.sqrt` is in core, with
its defining bounds available in mathlib as `Nat.sqrt_le'` and
`Nat.lt_succ_sqrt'` (stated with `^2`), which is literally the property the
randomised root tests sample. The division-algorithm identity
`Nat.div_add_mod : n * (m / n) + m % n = m` is what the multi-word div/mod
decompositions and the `times_word`/`times_overflow_word` product split reduce
to. `@monus_word` needs no machinery at all, since `Nat` subtraction is already
truncated; mathlib's general treatment of that is `tsub` with the `OrderedSub`
class, for the lemmas in their general form.

**Where Lean has it easier than Rust.** The wide operations invert the usual
difficulty. `div_triple_doubleword` and the triple/quadruple-word roots need
`num::BigUint` in Rust and `boost::multiprecision::uint256_t` in C++ purely
because 192- and 256-bit integers are not native types. In Lean, `Nat` is
arbitrary precision by construction, so those become ordinary `Nat` lemmas —
the specification of `div_triple_doubleword` is just a division identity about
$2^{128}n_1 + 2^{64}n_2 + n_3$, with no wide type to introduce and no separate
obligation to show the wide type is itself correct.

**What it would buy.** A theorem `∀ n1 n2 : UInt64, …` closes the quantifier
that property-based tests can only sample. The distinction is not academic
here: the C++ `add_with_carry_overflow_word` discussed above differs from the
checked version on exactly the pairs with $n_2 = 2^{64}-1$ — one $2^{64}$-th of
the input space, which a uniform random test will essentially never draw. Ten
thousand samples is good evidence about the typical case and almost none about
a failure set that thin.

**What it would not buy.** A Lean proof is a proof about a Lean model. Unless
that model is tied to the deployed code, `machine_word.rs` is certified only as
far as the transcription is faithful — and transcription is exactly where such
errors hide. Tooling exists to close the gap from the Rust side: Aeneas,
together with Charon, translates a safe subset of Rust through an MIR-derived
intermediate language into a pure functional Lean 4 model, so the object of the
proof is derived from the source rather than written out by hand. Whether all
of `machine_word.rs` — `num::BigUint` included — falls inside that subset is an
open question; the single-word half of it, plain `u64` arithmetic with no loops
and no allocation, plainly does.

Such a proof would complement, not replace, the Kani proofs `merc` already
runs. Kani model-checks the actual Rust through MIR, which is what `merc` uses
for unsafe-code invariants and for small total functions — `merc_number` itself
carries `#[kani::proof]` harnesses for `bits_for_value` (over every `usize`)
and for the power-of-two helpers (over every `u16`). Its reach stops where
bounded model checking stops: the wide identities involve heap-allocated
arbitrary-precision values and loops bounded only by the operand size, which is
not what a BMC tool is for, whereas `Nat` states them directly. The natural
division of labour is Kani on the code as compiled, and Lean on the arithmetic
that code is supposed to implement.

## Native evaluation in the rewriter

Because `@word` operations have no equations, a rewrite engine cannot reduce
`@add_word(w1, w2)` by matching rules — there are none. Name resolution happens
once, when the `RewriteSpecification` is built from the data specification:
`MachineWordOp::from_name` maps each `@`-prefixed symbol to an operation, and
the `SetAutomaton` stores the resolved operation on that symbol's transition,
so nothing on the hot path ever inspects a string. `InnermostRewriter` (and
`NaiveRewriter`) fire it when a term's own head symbol carries one, calling
`MachineWordOp::evaluate`, which computes the result directly once the
arguments are concrete `MachineNumber`s — or, for `@shift_right`'s first
argument, a `true`/`false` literal — and otherwise leaves the application
untouched. This mirrors mCRL2's own `jitty`/`jittyc` dispatch to compiled C++
instead of rewrite rules. Since a machine number carries no function symbol of
its own for the automaton to key a transition on, `merc_sabre`'s `SetAutomaton`
matches every machine number under one shared stand-in symbol
(`machine_number_symbol`, spelled `@machine_number@`, in
`set_automaton/automaton.rs`) — enough to know *that* a position holds a
digit, which is all any bundled rule's left-hand side needs.

!!! note "`InnermostRewriter` for now"
    The bundled end-to-end tests
    (`crates/sabre/tests/number_encoding_tests.rs`) exercise
    `NumberEncoding::MachineWord` through `InnermostRewriter`, not
    `SabreRewriter` — building its set automaton does not currently reach a
    fixpoint in practice on even trivial `MachineWord` terms, due to
    combinatorial blow-up from the recursive digit-chain pattern shape (a
    separate concern from the partition-merge defect the construction used to
    have — see [The Sabre Set Automaton](set-automaton.md)). Prefer
    `InnermostRewriter` when selecting the machine-word encoding until that is
    addressed.

## References

- `merc`: [`machine_word.rs`](https://github.com/MERCorg/merc/blob/main/crates/number/src/machine_word.rs),
  [`machine_word_evaluation.rs`](https://github.com/MERCorg/merc/blob/main/crates/data/src/machine_word_evaluation.rs),
  [`number_encoding.rs`](https://github.com/MERCorg/merc/blob/main/crates/typecheck/src/number_encoding.rs),
  [`machine_word.mcrl2`](https://github.com/MERCorg/merc/blob/main/crates/syntax/spec/machine_word.mcrl2),
  [`pos64.mcrl2`](https://github.com/MERCorg/merc/blob/main/crates/syntax/spec/pos64.mcrl2),
  [`nat64.mcrl2`](https://github.com/MERCorg/merc/blob/main/crates/syntax/spec/nat64.mcrl2),
  [`number_encoding_tests.rs`](https://github.com/MERCorg/merc/blob/main/crates/sabre/tests/number_encoding_tests.rs)
- mCRL2: [`machine_word.spec`](https://github.com/mCRL2org/mCRL2/blob/master/scripts/code_generation/data_types/machine_word.spec),
  [`pos64.spec`](https://github.com/mCRL2org/mCRL2/blob/master/scripts/code_generation/data_types/pos64.spec),
  [`detail/machine_word.h`](https://github.com/mCRL2org/mCRL2/blob/master/libraries/data/include/mcrl2/data/detail/machine_word.h),
  [`machine_word.cpp`](https://github.com/mCRL2org/mCRL2/blob/master/libraries/data/source/machine_word.cpp),
  [`rewrite_large_numbers_test.cpp`](https://github.com/mCRL2org/mCRL2/blob/master/libraries/data/test/rewrite_large_numbers_test.cpp)
  (the identities `number_encoding_tests.rs` ports)
- Lean: [mathlib4 documentation](https://leanprover-community.github.io/mathlib4_docs/),
  [Aeneas](https://github.com/AeneasVerif/aeneas)
