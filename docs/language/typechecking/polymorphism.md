# Type variables and polymorphic schemes

[The system-defined specification](system-specification.md) explains why the
comparison operators, `if`, the container operations and function update are
typed as polymorphic schemes. This page defines schemes and their instances, and
states why the equations of a template need to be checked only once. It assumes
the definitions of the preceding pages, from
[Sort and name resolution](name-resolution.md) to
[The system-defined specification](system-specification.md).

## Type variables

A *template* is a piece of mCRL2 text that declares polymorphic operations and
their defining equations, such as the bundled `list.mcrl2`, `set.mcrl2`,
`fset.mcrl2`, `bag.mcrl2`, `fbag.mcrl2` and `comparison.mcrl2`. A template
declares its sort variables in a `type_var` block, the way a `var` block declares
data variables:

```mcrl2
type_var S;
map in: S # List(S) -> Bool;
```

Type-variable resolution runs early, before sort names are resolved (see the
[pipeline](index.md#architecture)). It assigns every `type_var` declaration a
*type-variable identifier* and replaces every reference to it by that identifier,
just as [Sort and name resolution, Definition 2](name-resolution.md#def-sort-name-resolution) does for sort names. A reference to an undeclared type
variable, and a `type_var` block that declares a name twice, are rejected. Every
template is resolved immediately after it is parsed, so no later pass sees an
unresolved type variable.

User specifications do not declare type variables; `type_var` blocks only occur
in templates.

## Schemes and instances {#schemes-and-instances}

<a id="def-scheme"></a>**Definition 1 (scheme).** A *scheme* $\forall \alpha_1 \ldots \alpha_k.\ s$ is a
sort $s$ in which the type variables $\alpha_1, \ldots, \alpha_k$ may occur, at
any depth. Every constructor and mapping declaration of a template is a scheme,
which binds the type variables that occur in its sort.

A type variable is a member of the [sort lattice](sort-inference.md#the-subsort-order),
resolved and interned like any other sort, so `in: S # List(S) -> Bool` is one
interned sort in which both occurrences of `S` are the same type variable. A
scheme is stored as just that sort: its bound variables are not stored
separately, but are the type variables that occur in it.

<a id="def-instance"></a>**Definition 2 (instance).** An *instance* of a scheme $\forall \bar\alpha.\ s$
at one occurrence of its name is $s[\bar\alpha := \bar h]$, where $\bar h$ are
fresh holes ([The Unifier, Definition 1](inference/unification.md#def-sorts-with-holes)), one per type variable.

Within one instance, all occurrences of a type variable become the same hole, so
in `in: S # List(S) -> Bool` the element and the list agree on `S`. Different
occurrences of `in`, also in the same equation, get different holes, so they
are independent.

The schemes of the signature ([Signature and well-typedness, Definition 1](signature.md#def-signature)) come from the five container
templates and the comparison template, and from one function-update template per
arity. A function-update template has no bundled file: its text is generated for
each arity that the specification uses (and for arity one), while the
specification is type checked.

## Checking a template once {#checking-a-template-once}

The defining equations of a template, such as `@zero_ == @one_` in
`bag.mcrl2`, are checked once per template, and not once per instance. They are
checked by [sort inference](sort-inference.md) with the template's type
variables *rigid*: a type variable is treated as a sort constant that unifies
only with itself, and not as a hole.

<a id="thm-checking-a-template-once"></a>**Theorem 1 (checking a template once).** If the equations of a template are
well-typed with its type variables $\bar\alpha$ rigid, then for every
substitution $\bar\alpha := \bar s$ of sorts, the instantiated equations are
well-typed, with the typing obtained by applying the same substitution to the
typing of the template.

*Proof idea.* This is the substitution lemma behind let-polymorphism: a
derivation that treats $\alpha$ as an unknown constant uses no property of it,
so replacing $\alpha$ by $s$ throughout yields a derivation for $s$. It is not
formalised in Lean.

So `@zero_ == @one_` is never checked again for `Bag(Nat)` or `Bag(D)`. A
specification that uses several element sorts pays for checking each template
once. The result of checking a template, its type variables and the typing of
each equation, is kept on the checking context. At
[lowering](../rewriting/lowering.md#materializing-ground-content-at-lowering-time),
every ground instance is typed by substitution into it, instead of by inference.

All templates are checked while a
[`DataSpecification`](https://mercorg.github.io/merc/merc_typecheck/)
is built, also when the specification uses no container.

## Source locations

The ground instances that lowering generates from a template are registered in
the shared [source map](../parsing/source_map.md) as virtual documents, such as
`<builtin>/list.mcrl2`. The template text that the schemes themselves are built
from is not registered, so a use of a polymorphic operation has no declaration
location; see [Source locations](system-specification.md#source-locations).
