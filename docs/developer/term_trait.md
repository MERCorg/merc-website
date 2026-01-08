# The Term trait

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

This trait is rather complicated with two lifetimes, but this is used to support
both the `ATerm`, which has no lifetimes as it is owned, and `ATermRef<'a>`
whose lifetime is bound by `'a`. 


## Alternative

Consider the alternative of having a single lifetime `'a` in the `Term<'a>` trait.
In that case, we would have to implement `Term<'a>` for `ATermRef<'a>` for all lifetimes
`'a`, including the `'static` lifetime. 



This is done by requiring that `'b: 'a`,
so that we can implement `Term<'a, 'b>` for `&'b ATerm` for all lifetimes
where `'b: 'a`, and implement `Term<'a, 'b>` for `ATermRef<'a>`
for all lifetimes `'a` where `'b: 'a`. We use `trybuild` to verify that our
implementations are sound. 

Because now we can be require that `'b: 'a`
for the implementation of `Term<'a, 'b>` for `ATerm`, we can safely return
`ATermRef<'a>` from methods of `Term<'a, 'b>`.
Without the 'b: 'a` constraint, we would implement Term<'a> for ATerm, for
all lifetimes 'a, including the 'static lifetime, and this would be unsound.
Alternatively, we could have implemented Term<'a> for &'a ATerm, but then ATerm
cannot be used directly as a Term in many places.
