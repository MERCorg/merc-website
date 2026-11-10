# Protection sets

A *protection set* holds the garbage-collection roots of the term pool: every
owned `ATerm` keeps its term alive by having an entry in the protection set of
its thread (see [Terms](aterms.md)). It is implemented by
[`ProtectionSet`](https://mercorg.github.io/merc/merc_unsafety/struct.ProtectionSet.html)
in [`merc_unsafety`](https://mercorg.github.io/merc/merc_unsafety/index.html),
which stores its free slots as an intrusive list inside a `union`, so that
reading a slot is only defined if it reads the variant last written to it.
This page defines what a protection set means (Definition 1), how it is
represented (Definitions 2 to 5), and states the theorems that make its
`unsafe` reads sound, together with how far
[Kani](https://model-checking.github.io/kani/) checks them.

## Abstract protection sets

<a id="def-abstract-protection-set"></a>**Definition 1 (abstract protection set).** An *abstract protection set* over
a set of objects $T$ is a finite partial map $\sigma : \mathbb{N} \rightharpoonup
T$ from *indices* to objects; the indices in $\mathrm{dom}(\sigma)$ are *live*.
Its operations are:

- $\mathit{protect}(\sigma, x)$ returns an index $i \notin \mathrm{dom}(\sigma)$
  and the set $\sigma[i \mapsto x]$;
- $\mathit{unprotect}(\sigma, i)$, defined only for $i \in \mathrm{dom}(\sigma)$,
  returns $\sigma$ restricted to $\mathrm{dom}(\sigma) \setminus \{i\}$, and
  disposes of the object $\sigma(i)$;
- $\mathit{replace}(\sigma, i, x)$, defined only for $i \in \mathrm{dom}(\sigma)$,
  returns $\sigma[i \mapsto x]$;
- $\sigma(i)$ looks up a live index, and $i \in \mathrm{dom}(\sigma)$ tests
  whether $i$ is live.

These are the methods
[`protect`](https://mercorg.github.io/merc/merc_unsafety/struct.ProtectionSet.html#method.protect),
[`unprotect`](https://mercorg.github.io/merc/merc_unsafety/struct.ProtectionSet.html#method.unprotect),
[`replace`](https://mercorg.github.io/merc/merc_unsafety/struct.ProtectionSet.html#method.replace),
indexing and
[`contains_root`](https://mercorg.github.io/merc/merc_unsafety/struct.ProtectionSet.html#method.contains_root).
The garbage collector marks from every object in the range of $\sigma$, so a
term is a root exactly while some live index maps to it.

## Representation

<a id="def-representation"></a>**Definition 2 (representation).** A *concrete
protection set* is a triple $(R, h, s)$ of a sequence of *slots* $R = R_0 \ldots
R_{n-1}$, a *head* $h \in \mathbb{N} \cup \{\bot\}$ and a *size* $s \in
\mathbb{N}$. Every slot holds one of two variants: $\mathit{obj}(x)$ for an
object $x \in T$, or $\mathit{next}(j)$ for an index $j \in \mathbb{N}$.

In the code the slots are a `Vec` of a `union` of the object and a `usize`, so
each slot is the size of the larger of the two. The variant of a slot is not
stored anywhere: it is *ghost* state, determined by which field was last
written, and reading the other field is undefined behaviour when the bytes it
covers were not written as that type. The definitions below make the variant
explicit to state when a read is allowed.

<a id="def-freelist"></a>**Definition 3 (freelist).** The *freelist* of $(R, h,
s)$ is the sequence $f_0, f_1, \ldots$ with $f_0 = h$ and $f_{k+1} = j$ for
$R_{f_k} = \mathit{next}(j)$, which ends at the first $f_k$ with $R_{f_k} =
\mathit{next}(f_k)$, and is empty if $h = \bot$. It is *finite* if it ends, and
then $F$ denotes the set of its elements.

So the last free slot points to itself rather than to a sentinel value, which
keeps a free slot exactly one `usize` wide.

<a id="def-well-formed"></a>**Definition 4 (well formed).** A concrete
protection set $(R, h, s)$ with $n$ slots is *well formed* if

1. its freelist is finite, has at most $n$ elements, and all of them are below $n$;
2. $R_i$ is a $\mathit{next}$ variant for every $i \in F$, and an
   $\mathit{obj}$ variant for every $i < n$ with $i \notin F$;
3. $s + |F| = n$.

Conditions 1 and 3 can be evaluated at run time by following the freelist for
at most $n$ steps, and the Kani specification of `ProtectionSet` does exactly
that. Condition 2 is about ghost state and cannot be evaluated; Kani checks it
indirectly, see [Verification with Kani](#verification-with-kani).

<a id="lem-freelist-distinct"></a>**Lemma 1 (distinct freelist).** If the
freelist ends within $n$ steps, its elements are distinct; that is, $F$ has as
many elements as the freelist.

*Proof.* Each $f_{k+1}$ is determined by $f_k$ alone. If $f_a = f_b$ for $a <
b$ before the end, then the sequence repeats with period $b - a$ from $a$ on,
and since no element of $f_a, \ldots, f_{b-1}$ ends it, it never ends. ∎

This is why condition 1 needs no separate check for repetitions: following at
most $n$ steps and requiring the self-loop decides it. Proved on paper only.

<a id="def-abstraction"></a>**Definition 5 (abstraction).** The abstraction of a
well-formed $(R, h, s)$ is the abstract protection set $\alpha(R, h, s)$ with
domain $\{i < n \mid i \notin F\}$ that maps each such $i$ to the $x$ with
$R_i = \mathit{obj}(x)$. Its live indices number $n - |F| = s$.

## Theorems

<a id="thm-refinement"></a>**Theorem 1 (refinement).** Let $(R, h, s)$ be well
formed and $\sigma = \alpha(R, h, s)$.

1. `protect(x)` returns an index $i \notin \mathrm{dom}(\sigma)$ and results in a
   well-formed set with abstraction $\sigma[i \mapsto x]$. It reuses the slot
   $h$ when $h \neq \bot$, and appends a slot otherwise.
2. For $i \in \mathrm{dom}(\sigma)$, `unprotect(i)` results in a well-formed set
   whose abstraction is $\sigma$ without $i$, drops the object $\sigma(i)$
   exactly once, and puts slot $i$ at the head of the freelist.
3. For $i \in \mathrm{dom}(\sigma)$, `replace(i, x)` results in a well-formed set
   with abstraction $\sigma[i \mapsto x]$, and indexing with $i$ returns
   $\sigma(i)$.

So every reachable state of a `ProtectionSet` is well formed: the empty set,
with no slots and $h = \bot$, is, and Theorem 1 preserves it.

<a id="thm-variant-safety"></a>**Theorem 2 (variant safety).** In a well-formed
set, every `unsafe` read of a slot reads the variant last written to it:

- `next` is read only from slots in $F$: by `protect`, at the head $h$, and by
  the walks along the freelist (by `contains_root`, iteration and drop);
- `object` is read only from slots not in $F$: by indexing and `unprotect` at a
  live index, and by iteration and drop, which skip $F$.

*Proof idea.* Each read site is restricted to $F$ or to its complement by
construction, so condition 2 of Definition 4 gives the variant, and Theorem 1
gives Definition 4 in every reachable state. Proved on paper only; the
restrictions are checked by inspection of the code.

<a id="rem-stale-indices"></a>**Remark 1 (stale indices in release builds).**
The precondition $i \in \mathrm{dom}(\sigma)$ of `unprotect` is stated in its
`# Safety` section, but `replace` and indexing are safe methods with the same
precondition. They rely on the generational index of
[`ProtectionIndex`](https://mercorg.github.io/merc/merc_unsafety/struct.ProtectionIndex.html):
[`GenerationCounter`](https://mercorg.github.io/merc/merc_utilities/struct.GenerationCounter.html)
records a generation per slot and
[`get_index`](https://mercorg.github.io/merc/merc_utilities/struct.GenerationCounter.html#method.get_index)
panics on an index whose slot was freed since it was issued. It does so only in
builds with debug assertions; in release builds the generation is not stored,
`contains_root` cannot tell a stale index from a live one, and `replace` or
indexing with a stale index reads or overwrites a slot in $F$. That breaks
condition 2 of Definition 4, after which Theorem 2 no longer applies. In
`merc_aterm` the indices are held by the owning handles (owned terms, terms
being sent, protected containers and function symbols), each of which
unprotects its index once when it is dropped, so this requires misusing the
`merc_unsafety` interface directly. That the term library never does so has not
been verified.

## Verification with Kani

The Kani harnesses and contracts are in the `protection_set` module of
`merc_unsafety`. They check Theorem 1 in two ways, with objects of type `u32`:

- **Contracts over arbitrary states.** `protect` and `unprotect` carry
  `kani::requires`/`kani::ensures` contracts stating Theorem 1 in terms of the
  run-time part of Definition 4 and of `contains_root` and `len`. Their
  `proof_for_contract` harnesses start from *every* concrete set with exactly
  $n$ slots that satisfies conditions 1 and 3, for each $n \leq 6$, rather than
  from the states reachable by a few operations. Cover goals check that these
  states include ones that mix free and live slots.
- **Agreement with a model.** A harness performs every sequence of three
  operations from the empty set, alongside an explicit abstract protection set,
  and checks after each step that the set is well formed, that the freelist is
  exactly the set of free indices of the model, that every live slot holds the
  model's object, and that `protect` never returns a live index. This is the
  run-time evidence for condition 2: the variant of a slot is known from the
  model, and the slots read as `next` are exactly those on the freelist.

Since `u32` has no destructor, neither checks that `unprotect` drops the object
exactly once; that part of Theorem 1 follows on paper from Theorem 2, as the
slot is in $F$ afterwards and dropping the set skips $F$.

Neither is a proof for all sizes: they check every state within the bounds.
The bounds matter. Planting a bug that makes `protect` point the head at the
slot it just filled is caught by the contract harnesses, but not by the model
harness, because exposing it needs a freelist of two slots, which takes five
operations to build.

| statement | status |
|---|---|
| Lemma 1 | proved on paper |
| Theorem 1, `protect` | checked by Kani for all well-formed sets with at most 6 slots, in builds without debug assertions |
| Theorem 1, `unprotect` | checked by Kani for all well-formed sets with at most 6 slots, in both build configurations |
| Theorem 1, all operations | checked by Kani against the model for all sequences of 3 operations, in both build configurations |
| Theorem 2 | proved on paper, from Theorem 1 |

The contract of `protect` is only stated without debug assertions: with them,
`protect` also writes to the generation counter's buffer, which is private to
`merc_utilities` and so cannot be named in the contract's `kani::modifies`
clause. The harnesses are run with Kani's `function-contracts` feature, which
the crate's `Cargo.toml` enables, and the `protect` contracts additionally with
debug assertions disabled:

```bash
cd crates/core/unsafety
CARGO_PROFILE_DEV_DEBUG_ASSERTIONS=false cargo kani --harness protect_contract
cargo kani --harness unprotect_contract
cargo kani --harness operations_refine_model
```

Kani's check for reads of uninitialised memory (`-Z uninit-checks`) would check
condition 2 directly, as a read of the wrong variant reads bytes that were never
written, but it does not yet support code that calls function pointers, which
includes every panic with a formatted message.
