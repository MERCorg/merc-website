```math_preamble

\usepackage{tikz}
\usetikzlibrary{babel}
```
# The ATerm Library

The ATerm library is a Rust library for working with annotated terms (ATerms),
inspired by the `C++` ATerm library in the [mCRL2](https://www.mcrl2.org/)
toolset. Although the `annotated` part is no longer relevant, the name has
stuck.

## Function symbols

Function symbols are the building blocks of terms. Each function symbol has a
name and an arity (the number of arguments it takes). In the ATerm library,
function symbols are represented by the `Symbol` struct, which stores the name
and arity, and provides methods for comparison and hashing.

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

The `Term` trait, shown below in simplified form (the real trait declares
`protect`, `arg`, `arguments`, `copy`, `get_head_symbol`, `iter`, `index` and
`shared`), is the central trait for the ATerm library, allowing functions to be
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

This owned/borrowed split is not unique to the bare `ATerm`: every typed term
wrapper built on top of it, e.g. `merc_data`'s `DataExpression`, repeats the
same `copy()`/`protect()` pair, plus checked conversions from and to the raw
`ATerm`. The diagram below extends the picture with `DataExpression` and, one
level further down, the concrete `DataFunctionSymbol` (see [Data Terms and the
`merc_term` Macro](#data-terms-and-the-merc_term-macro) for how these wrapper
types, and the conversions between them, are generated):

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

## Data Terms and the `merc_term` Macro

`ATerm` and `ATermRef` are untyped: any function symbol applied to any
arguments is a valid term. Higher-level crates build *typed* wrappers on top,
e.g. `merc_data::DataExpression` and `merc_data::DataFunctionSymbol`, that
only accept terms with a particular shape, and add methods specific to that
shape (`DataFunctionSymbol::name()`, `DataFunctionSymbol::sort()`, ...). Every
such wrapper repeats the same owned/borrowed split described above.

### Declaring a wrapper

A module annotated with `#[merc_derive_terms]` may contain one or more
structs annotated with `#[merc_term(assertion)]`, each with a field named
`term` of type `ATerm`. `crates/data/src/data_expression.rs` declares
`DataFunctionSymbol` this way:

```rust
#[merc_derive_terms]
mod inner {
    // ...

    #[merc_term(is_data_function_symbol)]
    pub struct DataFunctionSymbol {
        term: ATerm,
    }

    impl DataFunctionSymbol {
        #[merc_ignore]
        pub fn new<N>(name: N) -> DataFunctionSymbol
        where
            N: Into<ATermString> + AsRef<str>,
        { /* ... */ }

        /// Returns the name of the function symbol
        pub fn name(&self) -> ATermStringRef<'_> {
            ATermStringRef::from(self.term.arg(0))
        }

        /// Returns the sort of the function symbol.
        pub fn sort(&self) -> SortExpressionRef<'_> {
            self.term.arg(1).into()
        }
    }
}
```

`is_data_function_symbol` is an ordinary predicate over any term, declared as
`fn is_data_function_symbol<'a, 'b, T: Term<'a, 'b>>(term: &'b T) -> bool`; the
macro wires it into a `debug_assert!` everywhere an `ATerm` is wrapped into a
`DataFunctionSymbol`, so an incorrectly-shaped term is caught close to where it
was constructed rather than as a confusing panic deep inside `name()` or
`sort()`. The argument is optional — a bare `#[merc_term]` generates exactly the
same code with no check at all — but every wrapper in the workspace names a
predicate, and anything other than a single identifier is rejected with a
`compile_error!`. The macro itself enforces the one structural requirement — a
field literally named `term` — with an `assert!` at macro expansion time, so
forgetting it is a compile error, not a runtime surprise.

`#[merc_term]` and `#[merc_ignore]` are themselves no-op attribute macros that
hand their input straight back; they exist purely as markers that
`#[merc_derive_terms]` reads off the items of the module it is applied to,
which is where all of the code generation happens.

### What gets generated

For the `DataFunctionSymbol` declaration above, `#[merc_derive_terms]` generates
(trimmed to the parts described in [Protected and Borrowed
Terms](#protected-and-borrowed-terms); see `merc_derive_terms.rs` for the
literal `quote!` template):

```rust
#[derive(Clone, Hash, PartialEq, Eq, PartialOrd, Ord)]
pub struct DataFunctionSymbol {
    term: ATerm,
}

impl DataFunctionSymbol {
    pub fn copy<'a>(&'a self) -> DataFunctionSymbolRef<'a> {
        self.term.copy().into()
    }
}

impl From<ATerm> for DataFunctionSymbol {
    fn from(term: ATerm) -> DataFunctionSymbol {
        debug_assert!(
            is_data_function_symbol(&term),
            "Term {:?} does not satisfy {}", term, "is_data_function_symbol"
        );
        DataFunctionSymbol { term }
    }
}

impl From<DataFunctionSymbol> for ATerm { /* unwraps `term`, unchecked */ }
impl std::ops::Deref for DataFunctionSymbol { type Target = ATerm; /* ... */ }
impl std::borrow::Borrow<ATerm> for DataFunctionSymbol { /* ... */ }
impl Markable for DataFunctionSymbol { /* mark/contains_term/contains_symbol/len */ }
impl std::fmt::Debug for DataFunctionSymbol { /* forwards to the ATerm's Debug */ }

impl<'a, 'b> Term<'a, 'b> for DataFunctionSymbol where 'b: 'a {
    // protect, arg, arguments, copy, get_head_symbol, iter, index, shared
    // all delegate to `self.term` via the `delegate!` crate.
}

#[derive(Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct DataFunctionSymbolRef<'a> {
    pub(crate) term: ATermRef<'a>,
    _marker: std::marker::PhantomData<()>,
}

impl<'a> DataFunctionSymbolRef<'a> {
    pub fn copy<'b>(&'b self) -> DataFunctionSymbolRef<'b> {
        self.term.copy().into()
    }

    pub fn protect(&self) -> DataFunctionSymbol {
        self.term.protect().into()
    }
}

impl<'a> From<ATermRef<'a>> for DataFunctionSymbolRef<'a> { /* same debug_assert! as above */ }
impl<'a> From<DataFunctionSymbolRef<'a>> for ATermRef<'a> { /* unwraps `term`, unchecked */ }
impl<'a> std::fmt::Debug for DataFunctionSymbolRef<'a> { /* ... */ }

// Note the `'_`: the delegated methods take a plain `&self` and hand back
// `ATermRef<'a>`, i.e. the lifetime the wrapper itself borrows from, not the
// lifetime of the borrow of `self`.
impl<'a, 'b> Term<'a, '_> for DataFunctionSymbolRef<'a> { /* delegates, as above */ }

impl<'a> std::borrow::Borrow<ATermRef<'a>> for DataFunctionSymbolRef<'a> { /* ... */ }
impl<'a> Markable for DataFunctionSymbolRef<'a> { /* ... */ }

// SAFETY: `DataFunctionSymbolRef` is a `#[repr(Rust)]` wrapper whose only
// non-zero-sized field is `ATermRef<'a>`, itself a lifetime-erasable handle
// into the global term pool.
unsafe impl Transmutable for DataFunctionSymbolRef<'static> { /* ... */ }
```

Every other `#[merc_term]`-annotated struct in the module — `DataVariable`,
`DataApplication`, `MachineNumber`, `DataEquation`, `DataAbstraction`,
`DataWhrDecl`, `DataWhereClause`, and `DataExpression` itself — expands the
same way, only the type name and the assertion predicate change.

The `Transmutable` impl on `DataFunctionSymbolRef<'static>` is what lets
`Protected<C>` (`crates/aterm/src/protected.rs`), a garbage-collector-rooted
container generic over any `C: Markable + Send + Sync + Transmutable +
'static`, store collections of typed wrappers — not just raw `ATermRef`s — and
hand back a correctly shortened lifetime through
`ProtectedReadGuard`/`ProtectedWriteGuard` on every access.

### Duplicating accessors onto the `..Ref` type, and `#[merc_ignore]`

For *every* `impl` block in the module that is not opted out (see below), the
macro also emits a clone of that block with the self type rewritten to
`..Ref<'_>`, so read-only accessors work
directly on a borrowed term without protecting it first — `name()`, `sort()`,
and `operation_id()` become callable on a `DataFunctionSymbolRef<'_>` for free,
with no extra code in `data_expression.rs`. This applies to trait impls just as
much as to inherent ones: `impl fmt::Display for DataFunctionSymbol` is what
gives `DataFunctionSymbolRef<'_>` its `Display`, which is why
`DataExpression`'s own `Display` can print a borrowed head symbol without
protecting it.

That duplication is not always sound or even meaningful. A function that
protects a brand-new term and returns it by value, like
`DataFunctionSymbol::new` or `DataFunctionSymbol::with_sort`, has no sensible
borrowed counterpart — there is no existing term to borrow from — so it is
tagged `#[merc_ignore]` and excluded, either for a whole `impl` block or for
individual functions within one that is otherwise duplicated.
`DataExpression::data_arguments` is the latter case: it is `#[merc_ignore]`d
inside the otherwise-duplicated `impl DataExpression` block and instead
hand-written again, directly, for `DataExpressionRef` later in
`data_expression.rs`, because the iterator it returns needs a signature tied to
`DataExpressionRef`'s own `'a` rather than to a fresh borrow of `&self`.

Because the rewrite is purely textual, the self type has to be a bare
identifier: `impl<T> Foo<T>` or `impl some::path::Foo` are rejected with a
`compile_error!` pointing at `#[merc_ignore]` as the escape hatch. The same
escape hatch is needed for anything in the module that is *not* a term wrapper
— `sort_terms.rs` marks `impl ContainerSortKind` (a plain enum) with
`#[merc_ignore]`, since there is no `ContainerSortKindRef` to duplicate it
onto.

### From the concrete type up to `DataExpression`, and back down

`DataExpression` is itself declared with `#[merc_term(is_data_expression)]`
in the same module, so it gets the exact same generated code as
`DataFunctionSymbol` — only `is_data_expression` accepts a broader set of
terms (any variable, function symbol, machine number, binder, where clause, or
application). The conversions between the two are hand-written, one
`#[merc_ignore]`d `impl` block per direction — the annotation being what stops
the macro from also emitting a nonsensical `impl From<DataFunctionSymbol> for
DataExpressionRef<'_>`:

```rust
#[merc_ignore]
impl From<DataFunctionSymbol> for DataExpression {
    fn from(value: DataFunctionSymbol) -> Self {
        value.term.into()
    }
}

#[merc_ignore]
impl From<DataExpression> for DataFunctionSymbol {
    fn from(value: DataExpression) -> Self {
        value.term.into()
    }
}
```

Both directions unwrap to the bare `term: ATerm` and re-wrap it, so both
re-run the target type's `debug_assert!` — widening to `DataExpression` can
never actually fail it (every function symbol is trivially a data
expression), but narrowing back to `DataFunctionSymbol` can, if the
`DataExpression` was, say, a variable. `DataVariable` has the same pair, plus
one further conversion written directly on the borrowed types,
`impl<'a> From<DataExpressionRef<'a>> for DataVariableRef<'a>`; the extended
diagram in [Protected and Borrowed Terms](#protected-and-borrowed-terms)
marks that direction with an asterisk on `DataFunctionSymbolRef` precisely
because it has not been written for that type yet.