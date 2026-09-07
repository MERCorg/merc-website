# Desugaring

Phase 1 of the pipeline turns surface syntax with special-cased structure into
plain applications and declarations, so every later phase has a single uniform
code path to walk instead of one special case per surface construct.

## Structured sorts

A `struct` declaration is desugared into an abstract sort plus its
constructors, recognisers, and projection functions. The defining equations
(recognisers, projections, and the `==`/`<`/`<=` orderings) are generated into
the [system-defined specification](system-specification.md) that accompanies
the user's specification, following Appendix B.10 of the book.

### Anonymous structs

An anonymous `struct` can appear inside a map/constructor sort, an equation
variable sort, or a binder annotation, without a top-level `sort X = struct
...;` declaring it. These are replaced by a reference to a named declaration
before the desugaring above runs, so that struct desugaring only ever has to
handle named structs. occurrence with a reference to a named declaration before
the desugaring above runs, so that struct desugaring only ever has to handle
named structs.

Two hoisting rules are needed, not one, because an anonymous struct's *meaning*
depends on whether it matches an already-declared struct:

- If the same struct body was already registered from a declaration-position
  `sort X = struct ...;`, the anonymous occurrence is hoisted to a reference to
  that existing declaration — reusing its name, and so its constructors — so
  that structurally identical structs share one sort.
- Otherwise, an anonymous `struct` gets a fresh nominal sort *for typing
  purposes only*. It does **not** add the struct's
  constructors/recognisers/projections to the global signature.

**Example.**

```mcrl2
sort D = struct c | d;
map f: struct c | d -> Bool;
```

Here `f`'s domain has the same body as the declared sort `D`, so it is hoisted
to a reference to `D` itself, and `f` can be applied to `c`/`d` — both already
exist as `D`'s constructors. Written in isolation, with no matching
declaration-position `sort D = ...;` anywhere in the specification, the same
`struct c | d` written as `f`'s domain instead hoists to a fresh, body-less
`@struct<n>` sort: `c` and `d` are never registered as constructors of
anything, so `f` would have no value it could ever legally be applied to —
exactly mirroring what the mCRL2 toolset itself does with an anonymous struct
sort.

## Operator lowering

Built-in operator syntax is lowered into plain applications — `x == y` becomes
`==(x, y)`, the list cons `[x]` becomes an application of the cons operator,
and so on — so that sort inference (Phase 3) has a single application code
path instead of a special case for every operator syntax form. Number and
container literals (`0`, `[]`, `{}`) are deliberately kept as their own
dedicated expression nodes rather than lowered to applications, because their
sort is chosen by inference itself (a literal's minimal admissible sort, an
empty container's element sort) rather than declared anywhere — there is no
application to lower them to.
