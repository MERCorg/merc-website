# Signature and well-typedness

This page defines the signature of a data specification, the well-typedness
conditions that [type checking](index.md) enforces on its declarations, and the
non-emptiness of sorts. It assumes
[Sort and name resolution, Definitions 1 to 4](name-resolution.md#def-variable-resolution) and
[Desugaring, Definitions 1 to 3](desugaring.md#def-structured-sort).

## The signature

<a id="def-signature"></a>**Definition 1 (signature).** The *signature* of a data specification is the
triple $(S, C, M)$ of Definition 15.1.5 of the book: the declared sorts $S$, and
the constructors $C$ and mappings $M$, each a set of pairs $f : s$ of a name and
a sort. A name may have several such pairs, its *overloads*, provided they differ
in sort; declaring exactly the same pair twice declares it once. In addition to
these ground overloads, a name can have *polymorphic schemes* ([Type variables and polymorphic schemes, Definition 1](polymorphism.md#def-scheme)),
such as `==` and the container operations.

The signature is computed once and shared by every later pass. Its sorts are the
interned sorts of the [sort lattice](sort-inference.md#the-subsort-order):
every declaration-level sort expression is mapped onto an interned sort when the
signature is built, and inference and lowering never look at a sort expression
again.

Schemes are kept apart from the ground overloads, in a table of their own keyed
by name, because a scheme is not a declaration: it has no constructor or mapping
identifier, and using it means [instantiating](polymorphism.md#schemes-and-instances) it.
Only constructing the signature and looking up a name during
[inference](sort-inference.md#resolving-names) need to know about schemes; every
consumer of ground overloads is unaffected by them.

## Well-typedness {#well-typedness}

<a id="def-well-typed-declarations"></a>**Definition 2 (well-typed declarations).** The declarations of a data
specification are *well-typed*, following Definition 15.1.7 of the book, if

1. a product sort occurs only as the domain of a function sort;
2. no name is both a constructor and a mapping;
3. no constant (a symbol without arguments) is declared with two different
   sorts;
4. no constructor has a basic sort or a function sort as its target;
5. no `var` block declares the same variable twice;
6. every sort is non-empty (Definition 3);

and moreover, as an mCRL2-specific rule, no user declaration redeclares a
system-defined symbol ([The system-defined specification, Definition 2](system-specification.md#def-reserved-names)).

The conditions are checked at two points of the pipeline, because they need two
views of the specification. Conditions 1 to 4 are checked while the signature is
built, before alias normalisation ([Sort and name resolution, Definition 4](name-resolution.md#def-sort-normal-form)), so that an error names a sort
as the user wrote it: `D`, not what `D` expands to. Conditions 5 and 6, and
condition 1 for equation variables, are checked after normalisation. Condition 6
needs the normalised view: a sort that is inhabited only through an alias, such
as `D` in `sort D = Nat;`, would otherwise be reported as empty. Each violation
is a variant of
[`WellTypedError`](https://mercorg.github.io/merc/merc_typecheck/).

## Non-empty sorts

<a id="def-non-empty-sorts"></a>**Definition 3 (non-empty sorts).** The set $N$ of *non-empty* sorts is the
least set such that

- every sort that is not the target of a constructor is in $N$: an abstract
  sort, an alias, a basic sort, a container sort or a function sort;
- a sort $s$ is in $N$ if some constructor $c : s_1 \# \dots \# s_k \to s$ has
  all its argument sorts $s_1, \ldots, s_k$ in $N$.

A sort that is the target of some constructor but not in $N$ is *empty*: every
constructor of it needs an argument of a sort that has no value, so no closed
term of that sort exists.

<a id="thm-computing-non-empty-sorts"></a>**Theorem 1 (computing non-empty sorts).** Let $N_0$ be the set of sorts of the
first clause of Definition 3, and $N_{i+1}$ be $N_i$ together with the sorts
that the second clause admits from $N_i$. Then $N_0 \subseteq N_1 \subseteq
\cdots$ reaches $N$ after at most $|S|$ steps.

*Proof idea.* The two clauses define a monotone operator on the finite lattice of
sets of sorts, whose least fixpoint is $N$ by the Knaster–Tarski theorem; Kleene
iteration from the least element reaches it, and every step that does not stop
adds at least one of the $|S|$ sorts. This is a standard argument, not
formalised in Lean.

The type checker computes $N$ by this iteration, and rejects every empty sort.
