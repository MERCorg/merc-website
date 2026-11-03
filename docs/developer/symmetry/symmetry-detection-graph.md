```math_preamble

\usepackage{stmaryrd}
```
# Symmetry detection graph

The `merc_pbes` crate of merc's mCRL2-based tools (under `tools/mcrl2`, not the
[`merc_pbes`](https://mercorg.github.io/merc/merc_pbes/index.html) language
crate) finds the symmetries of a PBES by constructing its *symmetry detection graph* (SDG) and
handing it to GAP's `Digraphs` package, which computes a generating set of the
graph's automorphism group. This page states the theorem that makes this sound
(Theorem 1), defines the colouring that merc implements (Definitions 1 and 2),
and explains where and why it differs from the paper: M. Bartels, M. Laveaux,
T. Neele and T. Willemse, *Symmetry Reduction for Parameterised Boolean Equation
Systems* [BLNW]. The paper
defines the SDG $\mathcal{G}(\mathcal{E})$ and its colouring, and proves that
the restriction of an SDG automorphism to the parameters is a symmetry. That
proof rests on a few intermediate results that are referred to by their content
below: an automorphism $h$ maps the right-hand side $\varphi_X$ of an equation
to itself ($h(\varphi_X) \equiv \varphi_X$), it preserves vertex size, and it
acts on every predicate formula as the induced parameter permutation
($h(\varphi) \equiv \pi(\varphi)$).

<a id="thm-symmetries-from-automorphisms-blnw"></a>**Theorem 1 (symmetries from automorphisms; [BLNW]).** If $h$ is an automorphism of
the coloured SDG $\mathcal{G}(\mathcal{E})$, then the permutation $\pi$ of the
parameters that $h$ induces is a symmetry of $\mathcal{E}$.

Theorem 1 is proved in [BLNW] for the paper's SDG; it is not formalised in Lean.
merc's colouring refines the paper's in the ways below, and each section argues
why the steps of the proof still hold, or, for the update edges and PVI colours,
why the refinement is what makes them hold.

<a id="def-vertex-colouring"></a>**Definition 1 (vertex colouring).** merc colours a vertex $v$ of the SDG by the
pair $(C(v), C_{RHS}(v))$, where $C_{RHS}(v) = \{X \mid v = \varphi_X\}$ and
$C(v)$ is

- for a parameter: its sort;
- for a bound variable: its sort and its de Bruijn index;
- for a PVI $X(\ldots)$: the predicate variable $X$;
- for a quantifier, `lambda` or comprehension: its kind and the sorts it binds;
- for a function application or connective: its head symbol;
- for a machine-number literal: its value.

<a id="def-edge-colouring"></a>**Definition 2 (edge colouring).** merc colours an edge by one of

- a set of argument positions $\{i \mid t = t_i\}$, for an argument $t$ of a
  non-commutative function $f(t_1, \ldots, t_k)$;
- a multiplicity $k$, for an operand that occurs $k > 1$ times in a flattened
  sum or product;
- a non-empty set of *update roles* $\subseteq \{\mathit{pvi}, \mathit{data},
  \mathit{par}\}$, for the edges of an update vertex;
- no colour, for every other edge.

## Colouring bound variables

The paper's vertex colouring $C_\Phi$ sets `C(d_k) = par` for a PBES parameter and `C(x) = x` for every
other variable, i.e. every quantifier- or abstraction-bound variable. In the
theory we assume structural alpha renaming, i.e., bound variables can be
consistently renamed without changing the meaning of the PBES, and in
practice the names of bound variables are arbitrary, so colouring them by name
would discard most real symmetries.

The implementation therefore uses *de Bruijn indices*: a bound variable is
identified by its sort and by where it is bound, namely the number of variables
bound between the occurrence and its binder, so `0` is the innermost one.


A multi-variable binder `forall x, y. φ` binds like the nested `forall x. forall
y. φ`, so the variables are numbered in list order. Binders that list the same
variables in a different order are therefore not identified, which is sound but
forgoes some reduction.

The indices only help if vertices are *identified* up to alpha-equivalence as
well. Hash-consed mCRL2 terms are not, since renaming a bound variable gives a
different term, and also identify two different variables of the same name when
a binder shadows a parameter. Vertices are therefore interned by their
*structure*: bound variables are leaves keyed by sort and index,
and an inner vertex is keyed by its colour and by its (already interned)
children together with their edge colours. Consequently

- `exists a. a > n` and `exists b. b > n` are one vertex;
- a bound variable can reuse the name of a parameter. Occurrences are resolved by
  lexical scope with the innermost binder winning;
- every variable must be a parameter or bound, otherwise the PBES is not
  closed and an error is reported.

A PVI is keyed by its name and the vertices of its arguments, and its update
vertices are created at the point where it is visited, since its arguments can
refer to variables bound at that position.

## Parameter colour

The paper gives *every* parameter vertex the same colour, `par`, with no
further distinction (it assumes a single data type $D$ for all terms). merc's colour of a parameter
is its sort (Definition 1). This is required since mCRL2 allows operator overloading on sorts alone.

## The right-hand-side colour

Besides $C(v)$, every vertex has the paper's second, orthogonal colour component
$C_{RHS}(v)$. The colour handed to GAP is the pair of both (Definition 1), so two
vertices are only in the same colour class when they agree on $C(v)$ and on
$C_{RHS}(v)$.
Equations with syntactically identical right-hand sides share a vertex, which
is why this is a set.

It is what makes $h(\varphi_X) \equiv \varphi_X$ hold: a size
argument alone cannot exclude $h(\varphi_X) = \varphi_Y$ for the equally-sized
right-hand side of a *different* equation $Y$, but
$C_{RHS}(h(\varphi_X)) = C_{RHS}(\varphi_X)$ and $X \in C_{RHS}(\varphi_X)$
then force $\varphi_X = \varphi_Y$.

## Edge colours

The paper's edge-colouring case for a function application is:

$$C(f(t_1,\dots,t_k), t) = \begin{cases} \star & \text{if } f \text{ commutative} \\ \{i \mid \exists i \in [k].\ t = t_i\} & \text{else} \end{cases} \qquad C(e) = \star \text{ for all other edges } e \in E$$

Its type is a little awkward, since the same colour function $C$ is used for
vertices and edges, and the "no colour" label $\star$ is not a real colour. merc
colours edges separately (Definition 2). The set of argument positions matches
the paper's set-of-positions case exactly, including the
"repeated argument" reading: `n - n` produces one edge to `n` coloured `{1,2}`,
not two parallel edges. "No colour" merges the paper's two $\star$ cases
(commutative-function arguments, and all other edges).

## Update edges

The paper gives an update vertex $X_{i,k}$ three separate edges: to
$\mathsf{PVI}(X,i)$, to $\mathsf{data}(X,i,k)$, and to $d_k$. None of these
three edge families is covered by the explicit edge-colouring
case (it only handles a function application's argument edges), so they
all fall under the catch-all $C(e) = \bot$ for "all other edges" — the
paper leaves all three uncoloured.

merc instead gives each one a distinct role, with a colour that is a *set* of
roles (Definition 2).


This isn't just a labelling nicety. The proof of $h(\varphi) \equiv \pi(\varphi)$,
in its `X(t_1,...,t_n)` case, silently relies on an automorphism `h` mapping the `data(X,i,k)` edge to another
`data` edge, and the `d_k` edge to another parameter edge — the proof reads
off `h(t_k) = t'_{k'}` from "the edge `(X_{i,k}, t_k)`" as if `data` edges
can only map to `data` edges, and separately reads `π(d_k) = d_{π(k)}` off
the `(X_{i,k}, d_k)` edge the same way. With every update edge uncoloured
$\bot$, as the paper literally has it, nothing forces that alignment: an
automorphism respecting only `C(e) = \star` on all three families is free to
map a `data` edge onto what was a `par` edge (or a `pvi` edge) at the image
vertex, and the proof's implicit "same kind of edge" step is unjustified.
Colouring the three roles separately is what makes that step actually true: an
automorphism must map a $\{\mathit{data}\}$-coloured edge to a
$\{\mathit{data}\}$-coloured edge, by the definition of a coloured graph automorphism
(`C((h(v), h(u))) = C((v, u))`).

A secondary effect of the same mechanism: when a PVI copies a parameter
unchanged — e.g. `X(n)` inside `X`'s own equation — the `data` and parameter
targets are the *same* vertex, and the graph (per the paper's prose) has
"exactly one edge per vertex pair", so two of the three edges must coincide.
When two of the three targets are the same vertex, their role sets are united, so
a parameter-copy update vertex gets exactly two edges: a
$\{\mathit{pvi}\}$-coloured edge to the PVI vertex, and a
$\{\mathit{data}, \mathit{par}\}$-coloured edge to the shared target; never
three edges, and never a dropped role.

## PVI colours carry the predicate variable name

The paper colours a PVI vertex by the predicate variable it instantiates,
$C_\Phi(X(t_1,\dots,t_n)) = X$, and so does merc (Definition 1). This is
necessary: a uniform colour for every PVI would drop the one thing the PVI case
of the proof relies on: it concludes
$\llbracket h(X(\bar t))\rrbracket\eta\delta = \llbracket \bar t'\rrbracket\delta \in \eta(X)$
— membership in $\eta(X)$ specifically — which only equals
$\llbracket \pi(X(\bar t))\rrbracket\eta\delta$ if the image PVI also
instantiates $X$. With a uniform colour, `X = Y(n) && Z(n)` has an automorphism
swapping `Y(n)` and `Z(n)` even though `Y` and `Z` are defined differently.
Carrying the name rules this out by construction, and cannot lose a genuine symmetry since the group action
on predicate formulas preserves predicate variable names.

## Deduplicating repeated PVI occurrences

The paper introduces update vertices `updates(E) = {X_{i,k} | X ∈
bnd(E), 1 ≤ i ≤ npred(X), 1 ≤ k ≤ n}` — one fan of update vertices for
*every* occurrence $i$ of a predicate variable instance in a right-hand side,
counted with multiplicity. merc instead generates one fan per distinct PVI term,
so `Y(n) && Y(n)` gets one fan of update vertices, not two. This is sound: the
paper's construction would give the shared PVI vertex two identical fans, and
those only enlarge the automorphism group by permutations of the duplicated fans,
which restrict to the identity on parameters. So the extra automorphisms the paper's construction would
admit here are exactly the ones that don't change the induced symmetry, so
dropping them costs nothing.

## Constructs beyond the paper's grammar

The paper's predicate formula grammar has exactly two Boolean connectives ($\vee, \wedge$)
and single-variable PBES-level $\forall/\exists$. The implementation covers
the larger surface a real mCRL2 PBES can contain:

- **`!` and `=>`** get their own colours alongside `&&` and `||`. `=>` is treated
  as non-commutative, its two edges coloured $\{1\}$ and $\{2\}$, since
  `a => b` differs from `b => a`.
- **Associative-commutative flattening**: an `&&`/`||`/`+`/`*`/`max`/`min`
  chain is flattened into a *single* n-ary vertex, as suggested by the paper. The
  paper's $\mathsf{sub}^\sharp$ is a *set*, which silently forgets how often an
  operand occurs. This is harmless for the idempotent operators
  (`&&`, `||`, `max`, `min`), which get one uncoloured edge per distinct leaf,
  but unsound for `+` and `*`: `n + n + m` and `n + m + m` would have the same
  graph, so swapping `n` and `m` would be reported as a symmetry. For these the edge to a repeated operand is coloured by its multiplicity $k$
(Definition 2).
- **Multi-variable and data-level binders**: a quantifier is coloured by the list
  of sorts it binds rather than the paper's single sort `D`, and the same
  colouring is used for data-level `lambda` and set and bag comprehension
  binders, which have no counterpart in the paper's term grammar.
- **Machine-number literals** are coloured by their value, so
  an automorphism can't conflate two different constants — the paper's
  grammar treats `b : B` and other terms abstractly and never discusses
  literals.
- **Parameter and bound-variable sorts** are part of the colour (see above),
  since mCRL2 overloads function symbols by sort.
- **`where` clauses are rejected outright** with an error. PBES standard
  form never produces one, but a user-supplied PBES can; the paper's grammar
  has no such construct to begin with.
