```math_preamble

\usepackage{tikz}
```
# The ATerm Library

 > ⚠️ **important** This documentation is WIP.

The ATerm library is a Rust library for working with annotated terms (ATerms),
inspired by the `C++` ATerm library in the [mCRL2](https://www.mcrl2.org/)
toolset. Although the `annotated` part is no longer relevant, the name has
stuck.

## Maximal Sharing

A term $f(t_1, \ldots, t_n)$ consists of a function symbol $f$ and subterms
$t_1$ to $t_n$, which means that terms are directed acyclic graphs. All terms
live in a single global term pool that guarantees *maximal sharing*: when a
term is constructed, the pool first checks whether a structurally equal term
already exists and returns the existing one if so (also known as *hash
consing*). As a consequence structural equality coincides with pointer
equality, so comparing or hashing terms is a single pointer operation, and
common subterms are stored only once.

Terms are garbage collected: the pool tracks the set of live *root* terms, and
unreachable terms are reclaimed in a mark-and-sweep pass. Every thread that
constructs terms registers a thread-local `ThreadTermPool` with the global
pool, holding the *protection sets* containing that thread's roots. Garbage
collection requires exclusive access to the pool: term construction takes a
(recursive) read lock, and collection takes the write lock, marking the terms
in every registered protection set and sweeping the rest. To amortize the cost
of collection, it is triggered by a budget derived from the pool's free
capacity that threads count down as they insert new terms.

## The Term Trait

The `Term` trait, shown below, is the central trait for the ATerm library,
allowing functions to be defined on generic terms, either owned or borrowed.
 
``` rust
pub trait Term<'a, 'b>
where
    'b: 'a,
{
    /// Functions taking 'b for self and return a reference with lifetime 'a.
    fn function(&'b self) -> ATermRef<'a>;
}
```

This trait is rather complicated with two lifetimes, but this is used to allow
implementing it for both the `ATerm`, which has no lifetimes as it is owned, and
`ATermRef<'a>` whose lifetime is bound by `'a`. 

This is done by requiring that `'b: 'a`, so that we can implement `Term<'a, 'b>`
for `ATerm`, and implement `Term<'a, 'b>` for `ATermRef<'a>`. Because we can
require that `'b: 'a` for the implementation of `Term<'a, 'b>` for `ATerm`,
we can safely return `ATermRef<'a>` from methods of `Term<'a, 'b>`. We use
[trybuild](https://crates.io/crates/trybuild) to verify that our implementations
are sound. 

Without the `b: 'a` constraint, we would implement `Term<'a>` for `ATerm`, for
all lifetimes `'a`, including the `'static` lifetime, and this would be unsound.
Alternatively, we could have implemented `Term<'a>` for `&'a ATerm`, but then
`ATerm` cannot be used directly as a `Term` in many places.

## Protected and Borrowed Terms

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


<div align="center">

```math

\begin{tikzpicture}

\node[draw, rounded corners=6pt, minimum width=3.2cm, minimum height=1cm, align=center] (ATerm) at (0,0) {ATerm};
\node[draw, rounded corners=6pt, minimum width=3.2cm, minimum height=1cm, align=center] (ATermRef) at (0,-4) {ATermRef};
\draw[->, thick, bend right=30] (ATerm)    to node[left]{copy()} (ATermRef);
\draw[->, thick, bend right=30] (ATermRef) to node[right]{protect()} (ATerm);

\end{tikzpicture}
```

</div>

Since protection goes through the thread-local pool, `ATerm` is deliberately
**not `Send`**: moving one to another thread would leave its root entry behind
in the wrong thread's protection set. It is `Sync`, since terms themselves are
immutable and cloning yields a locally protected copy.

## Sending Terms Between Threads

To transfer a term to another thread, `ATermSend` takes ownership of an
`ATerm` and re-protects it in a dedicated *send* protection set that is shared
behind an `Arc<Mutex<...>>` rather than being thread-local. Dropping an
`ATermSend` only locks that shared set, so it may be dropped on any thread.
The global pool furthermore keeps the send protection set of an exited thread
registered as long as such terms are alive, so an `ATermSend` may safely
outlive the thread that created it.

## Terms in Thread-Local Storage

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