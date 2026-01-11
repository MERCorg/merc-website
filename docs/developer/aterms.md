```math_preamble

\usepackage{tikz}
```

# The ATerm Library

The ATerm library is a Rust library for working with annotated terms (ATerms),
inspired by the `C++` ATerm library in the [mCRL2](https://www.mcrl2.org/)
toolset. Although the `annotated` part is no longer relevant, the name has
stuck.

```math

\begin{tikzpicture}

\node[draw, rounded corners=6pt, minimum width=3.2cm, minimum height=1cm, align=center] (ATerm) at (0,0) {ATerm};
\node[draw, rounded corners=6pt, minimum width=3.2cm, minimum height=1cm, align=center] (ATermRef) at (0,-4) {ATermRef};
\draw[->, thick, bend left] (ATerm)    -- node[left]{copy()} (ATermRef);
\draw[->, thick, bend left] (ATermRef) -- node[right]{protect()} (ATerm);

\end{tikzpicture}
```


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
for `ATerm`, and implement `Term<'a, 'b>` for `ATermRef<'a>`. Because now we can
be require that `'b: 'a` for the implementation of `Term<'a, 'b>` for `ATerm`,
we can safely return `ATermRef<'a>` from methods of `Term<'a, 'b>`. We use
[trybuild](https://crates.io/crates/trybuild) to verify that our implementations
are sound. 

Without the `b: 'a` constraint, we would implement `Term<'a>` for `ATerm`, for
all lifetimes `'a`, including the `'static` lifetime, and this would be unsound.
Alternatively, we could have implemented `Term<'a>` for `&'a ATerm`, but then
`ATerm` cannot be used directly as a `Term` in many places.