# Typing information

Editor tooling, such as hover and go-to-definition in a language server, needs the
results of [type checking](index.md) by source position: which sort an expression
has, and which declaration a name refers to. This page defines the typing
information that [`merc_typecheck`](https://mercorg.github.io/merc/merc_typecheck/index.html)
exposes for that purpose, and how it is obtained. It assumes the definitions
of the preceding pages of this section. An experimental language server built on it lives at
[MERCorg/merc-lsp](https://github.com/MERCorg/merc-lsp).

## Definitions

<a id="def-typing-information"></a>**Definition 1 (typing information).** The *typing information* of a
specification, or of one equation or expression, is a sequence of *typed nodes*,
one per checked expression node in generation order ([Sort inference, Definition 3](sort-inference.md#def-constraints)), and one per
name occurrence that is not part of a data expression. A typed node consists of

- its *span*: its position in the original source;
- optionally its *sort*, the inferred sort, as a sort expression for display;
- optionally its *resolved name*: what the identifier at this node refers to,
  with the span of its declaration when it has one.

A resolved name is one of the following.

| resolved name | refers to |
|---|---|
| variable | a binder ([Sort and name resolution, Definition 1](name-resolution.md#def-variable-resolution)) |
| constructor, mapping | a user declaration |
| system-defined | a basic-sort operation of Appendix B ([The system-defined specification, Definition 1](system-specification.md#def-system-defined-specification)) |
| built-in | a polymorphic operation ([Type variables and polymorphic schemes, Definition 1](polymorphism.md#def-scheme)), without a declaration |
| action, process | a declared action or process |
| action set | every declaration of an action name in `hide`, `block`, `allow`, `comm` or `rename` |
| propositional variable | a PBES or PRES equation |
| state variable | the binder of a fixpoint variable in a state formula |
| sort | a sort declaration, for a sort name written by the user |

<a id="def-lookup-by-offset"></a>**Definition 2 (lookup by offset).** The typed node *at* a byte offset $o$ is,
among the typed nodes whose span $[b, e]$ satisfies $b \le o \le e$, the one with
the smallest span; among several with the smallest span, the last one in
generation order.

The end of a span counts as inside it, so that a cursor right after the last
character of a token still finds the token, as editors expect. Several nodes can
have the same span because a node that [operator lowering](desugaring.md#operator-syntax)
synthesises inherits the span of the surface expression it came from: `x + y`
and its synthesised `+` share one span, and the later, more specific node wins.

In merc, these are
`TypingInfo`,
`TypedNode`
and
`ResolvedName`,
and Definition 2 is `TypingInfo::at_offset`.

## Why typing information is keyed by span

Internally, inference keys its typing by the node numbering of the *lowered*
expression ([Sort inference, Definition 3](sort-inference.md#def-constraints)), which contains synthesised nodes without a
counterpart in the syntax tree that a caller parsed. A caller therefore cannot
reconstruct that numbering by walking its own tree, and typing information is
keyed by span instead.

The sort of a typed node is reconstructed from the resolved sort and has no
source position of its own: name resolution and alias normalisation
([Sort and name resolution, Definition 4](name-resolution.md#def-sort-normal-form)) discard or move the spans of sort expressions. A sort written by
the user is therefore recorded separately, as a node with a resolved *sort*
name, whose span is captured before normalisation. A typed node has no sort for
an action or process occurrence, whose declared argument sorts are a domain and
not the sort of a value, and for a sort-name occurrence, which is not a data
expression.

## Two ways of resolving a name

A variable occurrence is resolved by the syntactic pass of [Sort and name resolution, Definition 1](name-resolution.md#def-variable-resolution), before
type checking, because which binder it refers to follows from the syntax alone.
The resolved occurrence carries the span of its binder, so a variable's
declaration is known without consulting inference.

Constructor, mapping, action and process names can be overloaded, and which
declaration they refer to depends on the inferred sorts of their arguments. They
are resolved by the type checker itself, and recorded once a unique candidate
has been chosen. An action name in an action set has no arguments to choose an
overload by, so all its declarations are recorded, in declaration order, and the
editor decides what to do with several. A propositional variable is never
overloaded, since a PBES or PRES declares each at most once, and is recorded at
the span of its identifier.

## Typing information per specification

`DataSpecification::typing_info`
returns the typing information of all user equations, together with the sort
names written in the declarations;
`DataSpecification::equation_typing_info`
returns that of one equation, without the sort names, since a declaration does
not belong to one equation. An expression checked on its own, by
`DataSpecification::typecheck_expression_with_typing`,
comes with typing information of its own. Its variable identifiers and binder
spans come from a separate resolution call ([Sort and name resolution, Definition 1](name-resolution.md#def-variable-resolution)), so its typed nodes
must not be combined with the variable tables of another call.

`ProcessSpecification`
and
`ModalSpecification`
extend the typing information of their data specification with the expressions
they check themselves, such as action arguments, conditions, time stamps and
quantifier binders, and the action, process and fixpoint-variable names they
resolve. The PBES and PRES specifications of `merc_pbes` and `merc_pres` do the
same for propositional variables. See
[Specification type checking](../specification/index.md).
