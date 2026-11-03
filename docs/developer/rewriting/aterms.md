```math_preamble

\usepackage{tikz}
\usetikzlibrary{babel}
```
# Terms

The [`merc_aterm`](https://mercorg.github.io/merc/merc_aterm/index.html) crate is a Rust library of maximally shared
terms, inspired by the C++ ATerm library of the [mCRL2](https://www.mcrl2.org/)
toolset (the "A" stood for *annotated*, which no longer applies). Every term in
merc, such as a data expression, a PBES expression or a state of a state space,
is one. This page defines terms and maximal sharing (Definitions 1 and 2), and
describes how terms are kept alive and passed between threads. The pages of the
Rewriting section share one numbering of definitions and theorems.

## Terms and maximal sharing

**Definition 1 (term).** A *function symbol* is a pair $f/n$ of a name and an
arity. A *term* is $f(t_1, \ldots, t_n)$ for a function symbol $f/n$ and terms
$t_1, \ldots, t_n$. Terms are compared structurally: $f(t_1, \ldots, t_n) =
g(u_1, \ldots, u_m)$ iff $f/n = g/m$ and $t_i = u_i$ for all $i$.

**Definition 2 (maximal sharing).** A store of terms is *maximally shared* if no
two distinct entries are structurally equal.

All terms live in one global term pool, which is maximally shared: constructing a
term first looks up a structurally equal term and returns it if it exists (*hash
consing*). So terms form a directed acyclic graph in which common subterms are
stored once, and **structural equality is pointer equality**: comparing or
hashing a term is a single operation on its index, independent of its size. The
rest of merc relies on this, for example the [condition cache](condition-caching.md),
whose keys are terms.

Terms are garbage collected. The pool tracks a set of live *root* terms, and
unreachable terms are reclaimed by mark and sweep. Every thread that constructs
terms registers a thread-local pool with the global one, holding the *protection
sets* with that thread's roots. Collection needs exclusive access: constructing a
term takes a (recursive) read lock, and collection takes the write lock, marks
the terms reachable from every registered protection set and sweeps the rest. It
is triggered by a budget, derived from the free capacity of the pool, that
threads count down as they insert terms, which amortises its cost.

## The `Term` trait

The `Term` trait, shown below in simplified form — the real trait declares
several more accessors — is the central trait for the ATerm library, allowing functions to be
defined on generic terms, either owned or borrowed.
 
``` rust
pub trait Term<'a, 'b> {
    /// Functions taking 'b for self and return a reference with lifetime 'a.
    fn function(&'b self) -> ATermRef<'a>;
}

impl<'a, 'b> Term<'a, 'b> for ATermRef<'a> { /* ... */ }

impl<'a, 'b> Term<'a, 'b> for ATerm
where
    'b: 'a,
{ /* ... */ }
```

This trait is rather complicated with two lifetimes, but this is used to allow
implementing it for both the `ATerm`, which has no lifetimes as it is owned, and
`ATermRef<'a>` whose lifetime is bound by `'a`. 

Note that `'b: 'a` is not a bound on the trait itself, but on the implementation
for `ATerm`; `ATermRef<'a>` implements `Term<'a, 'b>` for every `'b`. Because we
can require that `'b: 'a` for the implementation of `Term<'a, 'b>` for `ATerm`,
we can safely return `ATermRef<'a>` from methods of `Term<'a, 'b>`. We use
[trybuild](https://crates.io/crates/trybuild) to verify that our implementations
are sound. 

Without the `b: 'a` constraint, we would implement `Term<'a>` for `ATerm`, for
all lifetimes `'a`, including the `'static` lifetime, and this would be unsound.
Alternatively, we could have implemented `Term<'a>` for `&'a ATerm`, but then
`ATerm` cannot be used directly as a `Term` in many places.

## Protected and borrowed terms {#protected-and-borrowed-terms}

The two implementations of the `Term` trait correspond to the two ways of
holding a term, shown in the diagram below:

 - `ATerm` is an *owned* term: on construction its index is inserted into the
   current thread's protection set, making it a garbage collection root, and
   dropping it removes the entry again. This mirrors mCRL2's
   `aterm_protect`/`aterm_unprotect`, but tied to RAII instead of manual calls.
 - `ATermRef<'a>` is a *borrowed* term: just the shared index with a lifetime
   that ties it to the `ATerm` (or protected container) it was borrowed from.
   Creating and copying an `ATermRef` costs nothing and never touches the
   protection set, which matters in hot loops such as the rewriter. Because the
   root it was borrowed from keeps the term (and all its subterms) alive,
   `arg` and `copy` can hand out further `ATermRef<'a>` values freely.

Calling `protect()` upgrades a borrowed term into an owned one, and `copy()`
borrows an owned term.

This owned/borrowed split is not unique to the bare `ATerm`: every typed term
wrapper built on top of it, e.g. `merc_data`'s `DataExpression`, repeats the
same `copy()`/`protect()` pair, plus checked conversions from and to the raw
`ATerm`. The diagram below extends the picture with `DataExpression` and, one
level further down, the concrete `DataFunctionSymbol` (see [Typed terms](#typed-terms) for how these types, and the conversions
between them, are generated):

<div align="center">

```math

\begin{tikzpicture}[
  every node/.style={font=\small},
  lbl/.style={font=\scriptsize}
]

% -- Owned row --
\node[draw, rounded corners=6pt, minimum width=2.6cm, minimum height=1cm, align=center] (ATerm) at (0,0) {ATerm};
\node[draw, rounded corners=6pt, minimum width=3.4cm, minimum height=1cm, align=center] (DataExpression) at (5.2,0) {DataExpression};
\node[draw, rounded corners=6pt, minimum width=4.0cm, minimum height=1cm, align=center] (DataFunctionSymbol) at (11.2,0) {DataFunctionSymbol};

% -- Borrowed row --
\node[draw, rounded corners=6pt, minimum width=2.6cm, minimum height=1cm, align=center] (ATermRef) at (0,-4) {ATermRef};
\node[draw, rounded corners=6pt, minimum width=3.4cm, minimum height=1cm, align=center] (DataExpressionRef) at (5.2,-4) {DataExpressionRef};
\node[draw, rounded corners=6pt, minimum width=4.0cm, minimum height=1cm, align=center] (DataFunctionSymbolRef) at (11.2,-4) {DataFunctionSymbolRef};

% -- copy()/protect() within each column --
\draw[->, thick, bend right=30] (ATerm) to node[left, lbl]{copy()} (ATermRef);
\draw[->, thick, bend right=30] (ATermRef) to node[right, lbl]{protect()} (ATerm);

\draw[->, thick, bend right=30] (DataExpression) to node[left, lbl]{copy()} (DataExpressionRef);
\draw[->, thick, bend right=30] (DataExpressionRef) to node[right, lbl]{protect()} (DataExpression);

\draw[->, thick, bend right=30] (DataFunctionSymbol) to node[left, lbl]{copy()} (DataFunctionSymbolRef);
\draw[->, thick, bend right=30] (DataFunctionSymbolRef) to node[right, lbl]{protect()} (DataFunctionSymbol);

% -- ATerm <-> DataExpression (macro-generated, owned) --
\draw[->, thick, bend left=20] (ATerm) to node[above, lbl]{into (assert)} (DataExpression);
\draw[->, thick, bend left=20] (DataExpression) to node[below, lbl]{into} (ATerm);

% -- DataExpression <-> DataFunctionSymbol (hand-written, owned) --
\draw[->, thick, bend left=20] (DataExpression) to node[above, lbl]{into (assert)} (DataFunctionSymbol);
\draw[->, thick, bend left=20] (DataFunctionSymbol) to node[below, lbl]{into (assert)} (DataExpression);

% -- ATermRef <-> DataExpressionRef (macro-generated, borrowed) --
\draw[->, thick, bend left=20] (ATermRef) to node[above, lbl]{into (assert)} (DataExpressionRef);
\draw[->, thick, bend left=20] (DataExpressionRef) to node[below, lbl]{into} (ATermRef);

% -- DataExpressionRef <-> DataFunctionSymbolRef: not hand-written for this type yet --
\draw[->, thick, dashed, bend left=20] (DataExpressionRef) to node[above, lbl]{into (assert)*} (DataFunctionSymbolRef);
\draw[->, thick, dashed, bend left=20] (DataFunctionSymbolRef) to node[below, lbl]{into*} (DataExpressionRef);

\end{tikzpicture}
```

</div>

Every arrow that lands on a wrapper type (rather than on the raw `ATerm`/
`ATermRef`) runs a `debug_assert!` that the underlying term actually has the
expected shape, e.g. going from `DataExpression` to `DataFunctionSymbol`
panics in debug builds if the expression is not, in fact, a function symbol.
Going the other way, from `DataFunctionSymbol` to the looser `DataExpression`,
also runs a check, but it can never fail: every function symbol already *is* a
data expression. Only the arrows that land on the raw `ATerm`/`ATermRef`
columns are unchecked, since they merely unwrap the `term` field. The two
dashed arrows are starred because they are not hand-written for
`DataFunctionSymbolRef` today — only the narrowing direction
(`DataExpressionRef` to a concrete `..Ref`) has been written so far, for
`DataVariableRef`; reaching `DataFunctionSymbolRef` from a
`DataExpressionRef` therefore has to go through `ATermRef`, e.g.
`DataFunctionSymbolRef::from(Term::copy(&expression_ref))`. The explicit
`Term::copy` is needed because each wrapper also has an *inherent* `copy()`
that shadows the trait method and returns the wrapper's own `..Ref` type
rather than an `ATermRef`.

Since protection goes through the thread-local pool, `ATerm` is deliberately
**not `Send`**: moving one to another thread would leave its root entry behind
in the wrong thread's protection set. It is `Sync`, since terms themselves are
immutable and cloning yields a locally protected copy.

## Sending terms between threads

To transfer a term to another thread, `ATermSend` takes ownership of an
`ATerm` and re-protects it in a dedicated *send* protection set that is shared
behind an `Arc<Mutex<...>>` rather than being thread-local. Dropping an
`ATermSend` only locks that shared set, so it may be dropped on any thread.
The global pool furthermore keeps the send protection set of an exited thread
registered as long as such terms are alive, so an `ATermSend` may safely
outlive the thread that created it.

## Terms in thread-local storage

Since the protection mechanism itself lives in the thread-local
`THREAD_TERM_POOL`, terms stored in *other* thread-local variables interact
badly with thread teardown: Rust does not specify the order in which
thread-local destructors run, so the pool may be destroyed before a
thread-local that still holds an `ATerm`. Two things then happen, in order:

 1. The pool's destructor deregisters this thread's protection sets from the
    global pool, in this case all entries are inserted into a global protection
    set that is shared between all threads. Note that this is the safe option,
    but these terms will then never be reclaimed again.
 2. The `ATerm` destructor runs and calls `THREAD_TERM_POOL.with(..)` to
    unprotect itself. The standard library guarantees that accessing a destroyed
    thread-local *panics*, and a panic inside a thread-local destructor is a
    fatal runtime error that aborts the process.

There are two alternatives:

 - **`ATermSend`** does not touch the thread-local pool on drop and keeps its
   term registered as a root even after the creating thread has exited (see
   above), so it is safe to store in a thread-local — including reading it
   from other thread-local destructors.
 - **`ManuallyDrop<ATerm>`** suppresses the destructor entirely, avoiding the
   abort; can be used for terms that should be kept alive until the end of the
   program.

## Typed terms {#typed-terms}

`ATerm` and `ATermRef` are untyped: any function symbol applied to any arguments
is a term. Higher-level crates define *typed* terms on top, such as
[`DataExpression`](https://mercorg.github.io/merc/merc_data/)
and
`DataFunctionSymbol`
in `merc_data`, which accept only terms of a particular shape and add methods for
that shape. Each one repeats the owned and borrowed pair of
[Protected and borrowed terms](#protected-and-borrowed-terms).

Typed terms are generated by the attribute macros of
[`merc_macros`](https://mercorg.github.io/merc/merc_macros/index.html). In a
module marked
[`#[merc_derive_terms]`](https://mercorg.github.io/merc/merc_macros/attr.merc_derive_terms.html),
every struct marked
[`#[merc_term(predicate)]`](https://mercorg.github.io/merc/merc_macros/attr.merc_term.html)
with a single field `term: ATerm` becomes a typed term. The macro generates:

- the borrowed counterpart `..Ref<'a>`, with `copy()` and `protect()` between the
  two, and an implementation of `Term` for both that delegates to the underlying
  term;
- conversions from and to `ATerm` and `ATermRef`, where every conversion *into*
  the typed term checks `predicate` with a `debug_assert!`, so that a term of the
  wrong shape is caught where it is wrapped rather than deep inside an accessor;
- a copy of every `impl` block of the module with the self type replaced by the
  borrowed type, so that read-only accessors such as `name()` and `sort()` also
  work on a borrowed term without protecting it first. A function or block for
  which this is meaningless, such as a constructor that returns a new term, is
  excluded with
  [`#[merc_ignore]`](https://mercorg.github.io/merc/merc_macros/attr.merc_ignore.html).

The borrowed type also implements
`Transmutable`, which lets
`Protected`, a container that is a garbage-collection
root, store typed terms and hand them out with a lifetime shortened to the
access.

Conversions between two typed terms, such as from `DataFunctionSymbol` to
`DataExpression` and back, are written by hand and check the shape of the target
in the same way: widening to `DataExpression` cannot fail, narrowing to
`DataFunctionSymbol` fails, in debug builds, on a variable. Only some of these
conversions exist for the borrowed types (they are dashed in the diagram above);
a borrowed term can otherwise be converted through `ATermRef`.
