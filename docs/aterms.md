# The ATerm trait

The ATerm trait represents a first-order term in the ATerm library.
It provides methods to manipulate and access the term's properties.
 
```rust

pub trait Term<'a, 'b>
where
    'b: 'a,
{
    /// Functions taking 'b for self and return a reference with lifetime 'a.
    fn functions(&'b self) -> ATermRef<'a>;
}
```

This trait is rather complicated with two lifetimes, but this is used
to support both the [ATerm], which has no lifetimes, and [ATermRef<'a>]
whose lifetime is bound by `'a`. Because now we can be require that `'b: 'a`
for the implementation of [Term<'a, 'b>] for [ATerm], we can safely return
[ATermRef<'a>] from methods of [Term<'a, 'b>].
Without the 'b: 'a` constraint, we would implement Term<'a> for ATerm, for
all lifetimes 'a, including the 'static lifetime, and this would be unsound.
Alternatively, we could have implemented Term<'a> for &'a ATerm, but then ATerm
cannot be used directly as a Term in many places.
