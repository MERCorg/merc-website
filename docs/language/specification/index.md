# Specification type checking

A [data specification](../typechecking/index.md) covers only the data language.
This page defines how the specifications built on top of it are type checked:
process specifications and modal formulas in
[`merc_typecheck`](https://mercorg.github.io/merc/merc_typecheck/index.html), and
PBESs and PRESs in [`merc_pbes`](https://mercorg.github.io/merc/merc_pbes/index.html)
and [`merc_pres`](https://mercorg.github.io/merc/merc_pres/index.html). It
assumes the definitions of the [Type checking](../typechecking/index.md) section,
cited as "Type checking, Definition $n$".

All of them follow the same three steps.

1. **Resolve variables.** Every binder of the specification, such as a process
   parameter, a `sum` variable, a global variable or a quantifier, is resolved
   syntactically, as in Type checking, [Sort and name resolution, Definition 1](../typechecking/name-resolution.md#def-variable-resolution).
2. **Check the data specification** exactly as a standalone
   `DataSpecification`,
   and **collect the declarations** of the specification (actions, processes,
   propositional variables) into tables, so that resolving a name later is a
   lookup.
3. **Check every expression** of the specification against the sort it must
   have, resolving names against the declaration tables and the data signature.

Type checking covers sorts and names only. Properties such as the monotonicity of
a PBES, or its alternation depth, are separate analyses.

## Process specifications

<a id="def-action-and-process-declarations"></a>**Definition 1 (action and process declarations).** A process specification
declares actions and processes. A name may be declared several times as an
action, or several times as a process, with different argument sorts; these are
its *overloads*. A name may not be declared both as an action and as a process.

The last condition is needed because the grammar of mCRL2 uses one production
for both an action instance and a positional process instantiation: the parser
produces the same node for `a(e)` whether `a` is an action or a process. The
[disambiguation pass](../parsing/disambiguation.md) recognises process content
by whether a name is declared as an action or a process, but never decides which
of the two it is. With Definition 1, at most one of the two tables has an entry
for any name, so a use of the name is never ambiguous between the two.

<a id="def-resolving-an-instance"></a>**Definition 2 (resolving an instance).** An occurrence `a(e_1, ..., e_n)`
resolves to the overload of `a` with $n$ parameters whose parameter sorts the
arguments can be checked against. It is an error if no such overload exists, and
an ambiguity if more than one does.

Resolving an instance needs the sorts of its arguments, so it happens during type
checking, not in a syntactic pass. An ambiguity remains when the declarations do
not rule it out: with `act c: Nat; act c: Int;`, the instance `c(1)` checks
against both, since the literal admits both sorts.

The check of a process specification further covers every `proc` body and
`init`: `sum` and `dist` variables are in scope for the subterm they bind,
conditions are checked against `Bool`, time stamps and `dist` weights against
`Real`, and every communication `a | b -> c` is checked for compatible sorts.
Errors are reported as
`ProcessError`,
which includes the errors of the data specification. The result is a
`ProcessSpecification`.

## Modal formulas

A
`ModalSpecification`
is a state formula of the modal $\mu$-calculus, with its data specification and
action declarations. Its check resolves every action instance as in
Definition 2, every fixpoint variable to its enclosing `mu` or `nu` binder, and
scopes the data variables of quantifiers and of `inf`, `sup` and `sum`. A
`FormulaType`
selects the sort of the state-level `val(...)` expressions: `Bool` for an
ordinary formula and `Real` for a quantitative one.

## Equation systems

PBESs and PRESs are both *equation systems*: a sequence of fixpoint equations
over propositional variables, global variables, and an initial instantiation
(see [PBES](../pbes/pbes.md) and [PRES](../pbes/pres.md)). They differ only in
their formulas.

<a id="def-kind-of-equation-system"></a>**Definition 3 (kind of equation system).** A kind of equation system is given by

- its *value sort*: the sort that the data expressions embedded in a formula
  must have, `Bool` for a PBES and `Real` for a PRES;
- for every formula node, its *shape*: a data expression of the value sort (such
  as `val(e)`, or the constant of a constant multiplication in a PRES), an
  instantiation $X(e_1, \ldots, e_n)$, a binder of data variables (a quantifier,
  or `inf`, `sup` and `sum` in a PRES), or any other node, whose subformulas are
  checked on their own.

<a id="def-well-typed-equation-system"></a>**Definition 4 (well-typed equation system).** An equation system is well-typed
if its data specification is; no propositional variable has two equations; no
equation declares a parameter twice, and no global variable is declared twice;
no variable declaration uses an anonymous structured sort; every
instantiation, also the initial one, refers to a declared propositional variable,
with as many arguments as it has parameters, each checkable against the sort of
its parameter; and every data expression checks against the value sort, with the
variables of the enclosing binders, the equation's parameters and the global
variables in scope.

A propositional variable is never overloaded, so an instantiation either resolves
to its one equation or is an error.

In merc, Definition 3 is the trait
`EquationSystem`,
and the check of Definition 4 is written once, in
`Specification`,
for every kind of equation system. A PBES is
`PbesSpecification`
and a PRES is
`PresSpecification`,
both reporting
`EquationSystemError`.
Neither needs a disambiguation pass: their formulas have no syntax that two
different readings share, as a process body's conditions do.

## Typing information

Every kind of specification exposes the same
[typing information](../typechecking/typing-info.md) as a data specification,
extended with the expressions that its own check visits: action and process
arguments, conditions, time stamps and `dist` weights for a process
specification; `val(...)` expressions, instantiation arguments and binders for a
modal formula, a PBES or a PRES; and the action, process, fixpoint-variable and
propositional-variable names that the check resolves. It is collected during the
check itself, since that walk already visits every node.
