```math_preamble

\usepackage{stmaryrd}
```
# Symmetry Detection Graph

This section describes how to construct the *symmetry detection graph* (SDG) of
a PBES and hands it to GAP's `Digraphs` package to compute a generating set for
the PBES's symmetry group. Specifically, we explain the differences of the
implementation compared to the definitions and assumptions laid out in the
corresponding paper.

```todo
Add paper when it is published
```

## Colouring Bound Variables

Definition 3 sets `C(x) = par` for a PBES parameter and `C(x) = x` for every
other variable, i.e. every quantifier- or abstraction-bound variable. In the
theory we assume structural alpha renaming, i.e., bound variables can be
consistently renamed without changing the meaning of the PBES. The
implementation checks that all bound variables have unique names and do not
overlap with parameters, and then colours a bound variable
`VertexColour::BoundVariable` by its **sort only**, dropping the name entirely:

```rust
BoundVariable(SortExpression),
```

Colouring by sort is coarser than either alternative the paper considered — it
identifies branches up to α-equivalence, relying on the surrounding edge and
quantifier structure to pin down which bound variable is which — but it is what
makes the construction find anything on real input.

## Parameter Colour

Definition 3 gives *every* parameter vertex the same colour, `par`, with no
further distinction. `VertexColour::Parameter` instead carries the parameter's
sort. This is required since mCRL2 allows operator overloading on sorts alone.

## `C_eq`

Beyond `VertexColour`, `Sdg` tracks a second, orthogonal component per
vertex:

```rust
/// `C_eq(v)`: the set of equation indices whose right-hand side reaches
/// this vertex, indexed by `NodeIndex::index()`.
equations: Vec<BTreeSet<usize>>,
```

`to_gap_graph` folds both together into the colour it actually hands GAP
(`format!("{:?}|{:?}", colours[v], equations[v])`), so two vertices only end
up in the same GAP colour class when they agree on *both* `C(v)` and which
equations' right-hand sides reach them. `C_eq` has no counterpart in
Definition 3, and this is not a harmless extra restriction — it is what
makes Lemma 2 (`h(φ_X) = φ_X`) actually hold. The paper's proof of Lemma 2
argues purely from vertex size (Lemma 1: automorphisms preserve `|φ|`, and
`φ_X` is the largest subformula appearing in itself), which only rules out
mapping `φ_X` to a *proper* subformula of itself. It says nothing about
`h(φ_X) = φ_Y` for the equally-sized right-hand side of a *different*
equation `Y` — nothing in Lemma 1's size argument distinguishes two
right-hand sides of the same size, so as stated the proof doesn't exclude
that case, and Corollary 1 (which needs `h(φ_X) = φ_X` exactly, for every
`X`, to conclude `π` is a symmetry for the *whole* PBES) would not go
through without it.

With `C_eq` in the colouring, `h(φ_X) = φ_Y` forces `C_eq(φ_X) = C_eq(φ_Y)`.
Since every subformula's equation-set is a subset of the equation-sets of
the vertices reaching it, and `φ_X`/`φ_Y` are each the (unique, by size) top
vertex of their own right-hand side, `C_eq(φ_X) = C_eq(φ_Y)` forces each to
be a subformula of the other — hence `φ_X = φ_Y`, hence `X = Y`. This is
presumably what the draft's own margin note is circling when it weighs the
same idea and sets it aside: *"Some special colour for right-hand side makes
the proof easier. Otherwise, it could also be that only the semantics lemma
is needed."* The semantics lemma (Lemma 3) establishes that automorphisms
preserve semantics *given* `h(φ_X) = φ_X`; it does not by itself establish
that equality. `C_eq` is what does.

## Edge colours

Definition 3's edge-colouring case for a function application is:

$$C(f(t_1,\dots,t_k), t) = \begin{cases} \star & \text{if } f \text{ commutative} \\ \{i \mid \exists i \in [k].\ t = t_i\} & \text{else} \end{cases} \qquad C(e) = \star \text{ for all other edges } e \in E$$

The second margin note on the same page calls this out as unclear: *"This no
colour label `*` is not that clearly explained like this. The type of the
colour function is a bit awkward. Could we make it into a partial function
and not colour the edges that get a `*` now? Should we split up the
colouring functions for vertices and edges?"* The implementation answers all
three questions. `EdgeColour` is its own type, split out from
`VertexColour`:

```rust
enum EdgeColour {
    Argument(BTreeSet<usize>),  // C(f(t1,...,tk), ti) for non-commutative f
    Uncoloured,                 // the paper's `*`: commutative-function args
                                 // and every other edge
    Update(BTreeSet<UpdateRole>),
}
```

`Argument` matches Definition 3's set-of-positions case exactly, including the
"repeated argument" reading: `n - n` produces one edge to `n` coloured `{1,2}`,
not two parallel edges. `Uncoloured` merges the paper's two `\star` cases
(commutative-function arguments, and "all other edges") into one variant that is
never given a label at all — the "partial function" reading the margin note asks
about, implemented as an enum variant rather than an `Option`.

## Update edges

Definition 3 gives an update vertex $X_{i,k}$ three separate edges: to
$\mathsf{PVI}(X,i)$, to $\mathsf{data}(X,i,k)$, and to $d_k$. None of these
three edge families is covered by Definition 3's explicit edge-colouring
cases (those only handle a function application's argument edges), so they
all fall under the catch-all `C(e) = \star` for "all other edges" — the
paper leaves all three uncoloured.

The implementation instead gives each one a distinct role, via a colour that
is a *set* of roles:

```rust
enum UpdateRole { Pvi, Data, Par }
Update(BTreeSet<UpdateRole>)
```

This isn't just a labelling nicety. Lemma 3's `X(t_1,...,t_n)` case silently
relies on an automorphism `h` mapping the `data(X,i,k)` edge to another
`data` edge, and the `d_k` edge to another parameter edge — the proof reads
off `h(t_k) = t'_{k'}` from "the edge `(X_{i,k}, t_k)`" as if `data` edges
can only map to `data` edges, and separately reads `π(d_k) = d_{π(k)}` off
the `(X_{i,k}, d_k)` edge the same way. With every update edge uncoloured
`⋆`, as Definition 3 literally has it, nothing forces that alignment: an
automorphism respecting only `C(e) = \star` on all three families is free to
map a `data` edge onto what was a `par` edge (or a `pvi` edge) at the image
vertex, and the proof's implicit "same kind of edge" step is unjustified.
Colouring `Pvi`/`Data`/`Par` separately is what makes that step actually
true — an automorphism must map a `{Data}`-coloured edge to a
`{Data}`-coloured edge, by the definition of a coloured graph automorphism
(Definition 7: `C((h(v), h(u))) = C((v, u))`).

A secondary effect of the same mechanism: when a PVI copies a parameter
unchanged — e.g. `X(n)` inside `X`'s own equation — the `data` and parameter
targets are the *same* vertex, and the graph (per the paper's prose) has
"exactly one edge per vertex pair", so two of the three edges must coincide.
`add_update_vertices` inserts each of the three logical targets and lets
`add_or_merge_edge`/`merge_edge_colour` union the role sets when two land on
the same vertex, so a parameter-copy update vertex gets exactly two edges: a
`{Pvi}`-coloured edge to the PVI vertex, and a combined `{Data, Par}`-coloured
edge to the shared target — never three edges, and never a silently dropped
role (`test_update_edge_combines_roles_on_parameter_copy`).

## PVI Variables have no Name

Definition 3 colours a PVI vertex by the specific predicate variable it
instantiates: `C(X(t_1,...,t_n)) = X`. `VertexColour::Pvi` is a bare,
dataless variant — every PVI vertex, whether it's an occurrence of `X(...)`
or of an unrelated `Y(...)`, gets the *same* colour:

```rust
Pvi,
```

Lemma 3's PVI case needs the name: it concludes
$\llbracket h(X(\bar t))\rrbracket\eta\delta = \llbracket \bar t'\rrbracket\delta \in \eta(X)$
— membership in $\eta(X)$ specifically, not $\eta(Y)$ for whatever predicate
variable the image happens to instantiate — which is not the same as
$\llbracket \pi(X(\bar t))\rrbracket\eta\delta$ for an arbitrary automorphism
`h` unless the image PVI also instantiates `X`. Dropping the name from the
colour removes the one thing in Definition 3 that pins that down structurally.

In practice, every counterexample this would predict — an automorphism
mapping an `X(...)` PVI vertex onto a `Y(...)` PVI vertex — has to survive
the rest of the colouring too: `C_eq` (two PVI vertices for different
predicate variables essentially never reach the identical set of equations
by accident) and the fact that every PVI vertex is anchored to the same
global parameter vertices via its update vertices' `Par`-coloured edges make
such a swap hard to construct. No concrete counterexample is known. But
soundness resting on that as an accident of the rest of the construction is
not the same as the construction being sound by design. Adding the
predicate-variable name to `VertexColour::Pvi` would cost nothing — it can
only remove candidate automorphisms, never introduce one that wasn't already
being considered, and Definition 5's group action already preserves
predicate variable names, so no genuine symmetry is lost by requiring `h` to
preserve them too. This is currently documented as a known gap on
`VertexColour::Pvi` rather than fixed, pending a decision on whether to
tighten it.

## Deduplicating repeated PVI occurrences

Definition 3 introduces update vertices `updates(E) = {X_{i,k} | X ∈
bnd(E), 1 ≤ i ≤ npred(X), 1 ≤ k ≤ n}` — one fan of update vertices for
*every* occurrence $i$ of a predicate variable instance in a right-hand side,
counted with multiplicity. `build_sdg` instead deduplicates PVI occurrences
by ATerm identity before generating update vertices:

```rust
let mut seen_pvis: HashSet<PbesPropositionalVariableInstantiation> = HashSet::new();
for pvi in pbes_expression_pvi(&formula.copy()) {
    if seen_pvis.insert(pvi.clone()) {
        builder.add_update_vertices(e, &pvi, n)?;
    }
}
```

So `Y(n) && Y(n)` gets one fan of update vertices, not two
(`test_update_vertices_are_never_deduplicated` — the name refers to what
*does* still get its own fan: two occurrences that are only *equal*, not the
same ATerm). The code comment gives the soundness argument the paper doesn't
need to make, because it doesn't perform this optimization: *"The paper
instead ranges `i` over all `npred(X)` occurrences, which would give the
shared PVI vertex two identical fans of update vertices; those only enlarge
`Aut(G)` by permutations of the duplicated fans, which restrict to the
identity on parameters."* — i.e. the extra automorphisms Definition 3 would
admit here are exactly the ones that don't change the induced symmetry, so
dropping them costs nothing.

## Constructs beyond the paper's grammar

Definition 1's grammar has exactly two Boolean connectives ($\vee, \wedge$)
and single-variable PBES-level $\forall/\exists$. The implementation covers
the larger surface a real mCRL2 PBES can contain:

- **`not`/`imp`** get their own `Connective` colours alongside `And`/`Or`.
  `imp` is treated as non-commutative — its two edges are coloured
  `Argument({1})`/`Argument({2})` — since `a => b ≠ b => a`.
- **Associative-commutative flattening**: an `&&`/`||`/`+`/`*`/`max`/`min`
  chain is flattened into a *single* n-ary vertex with one uncoloured edge per
  leaf, via `is_flat_operator`/`flatten_associative`.
- **Multi-variable and data-level binders**: `VertexColour::Quantifier`
  carries a `Vec<SortExpression>` rather than Definition 3's single `D`, and
  the same colouring is reused for data-level `lambda` and set/bag
  comprehension binders (`Quantifier::Lambda`/`Comprehension`), which have no
  counterpart at all in Definition 1's term grammar.
- **Machine number literals** get a dedicated `MachineNumber(u64)` colour, so
  an automorphism can't conflate two different constants — the paper's
  grammar treats `b : B` and other terms abstractly and never discusses
  literals.
- **`where` clauses are rejected outright** with an error. PBES standard
  form never produces one, but a user-supplied PBES can; the paper's grammar
  has no such construct to begin with.
