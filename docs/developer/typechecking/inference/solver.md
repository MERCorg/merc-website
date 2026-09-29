```math_preamble

\usepackage{algpseudocode}
```
# Constraint Generation & the Solver

`crates/typecheck/src/inference/inference.rs` is the per-equation driver
built on top of [the `Unifier`](unification.md). It runs in two stages:
[`ConstraintGenerator`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.ConstraintGenerator.html) walks the AST once and emits a flat list of
[`Constraint`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html)s, then [`Solver`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.Solver.html) backtracks over that list, calling into
the `Unifier` at every choice point and keeping the single best leaf it
reaches.

## Top-level shape

```
infer(roots, declared_scope):
    unifier = Unifier::new()
    for (var, sort) in declared_scope:
        declared_sorts[var] = unifier.resolved_node(sort)

    expr_id_of = number_expr_nodes(roots)                   -- stable id per AST node
    expr_sorts = [unifier.fresh_var() for _ in expr_id_of]  -- one hole per node, up front

    generator = ConstraintGenerator { unifier, declared_sorts, expr_sorts, constraints: [], ... }
    generator.generate(roots)                                -- fills `constraints`; may unify eagerly

    constraints = merge_shared_subs(generator.constraints)   -- grouped Subs -> one Join each

    solver = Solver { unifier, constraints, expr_sorts, best: None,
                       default_sort: underdetermined_default_sort(role) }
    solver.solve(0)

    match solver.best:
        None                     -> Err(NoTyping)
        Some { duplicate: true } -> Err(AmbiguousExpression)  -- two leaves tied at the minimum measure
        Some { typing: Some(sorts, names) } -> Ok(EquationTyping { sorts, names, ... })
```

Every expression node — condition, left- and right-hand side of an equation,
or a single standalone expression — gets an [`ExprId`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/type.ExprId.html) assigned up front by
[`number_expr_nodes`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/fn.number_expr_nodes.html), in a fixed traversal order (parents before
children; an application's **arguments before its function**). `expr_sorts`
is pre-filled with one fresh unification variable per id before generation
even starts, so the generator's `visit` never mints a sort node itself — it
only looks one up by id. The argument-before-callee ordering is what makes
the search tractable: by the time the generator (and later the solver)
reaches a callee's overload choice, the argument holes are usually already
bound to something concrete, so most overloads fail to unify on the first
try.

## Constraint generation

[`ConstraintGenerator::visit`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.ConstraintGenerator.html#method.visit) recurses over the lowered expression tree and,
per node, either unifies eagerly (a structural fact that must hold in *every*
solution — a callee having a function sort, a condition being boolean — is
enforced immediately, so a violation is a direct error, not a silent search
failure) or pushes one [`Constraint`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html):

| Constraint | Fields | Meaning |
|---|---|---|
| [`Sub`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Sub) | `lhs, rhs: InferSortId` | `lhs` must be a subsort of `rhs` (an implicit up-cast) |
| [`Lit`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Lit) | `sort: InferSortId, kind: LitKind` | a numeric literal's sort must admit its kind (`Positive` or `Natural`; `0` can't be `Pos`) |
| [`Disjunction`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Disjunction) | `expr: ExprId, sort: InferSortId, disjuncts: [(NameTarget, InferSortId)]` | a name with several candidate overloads; the solver commits to exactly one |
| [`Comprehension`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Comprehension) | `body, node: InferSortId, element: ResolvedSortId` | `{x: S \| e}` reads as `Set(S)` (boolean body) or `Bag(S)` (numeric body) |
| [`Join`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Join) | `sources: [InferSortId], target: InferSortId` | the lattice least-upper-bound of several branches sharing one target |

Constraints are solved **in generation order**, not grouped by kind — this is
what makes "arguments before callee" actually pay off, since a `Disjunction`
for the callee is generated (and therefore solved) after the `Sub`/`Lit`
constraints for its already-visited arguments.

### Building a `Disjunction`: name resolution

[`gen_name`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.ConstraintGenerator.html#method.gen_name) resolves one `Id` occurrence. A declared variable (an
equation's own `var`, a binder, a process parameter) is looked up in
`declared_sorts` and bound to the node directly — no constraint needed, since
there is only one possible target. Otherwise
[`push_signature_disjuncts`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.ConstraintGenerator.html#method.push_signature_disjuncts) collects every candidate from the
[`Signature`](https://mercorg.github.io/merc/merc_typecheck/struct.Signature.html): each matching constructor/mapping overload becomes a
[`NameTarget::Op`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.NameTarget.html#variant.Op) disjunct with its own ground sort, and each matching
*scheme* (`==`, `<`, `if`, the polymorphic container operations, …) is
instantiated fresh via
[`instantiate_scheme`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.ConstraintGenerator.html#method.instantiate_scheme) — every
[`ResolvedSort::TypeVar`](https://mercorg.github.io/merc/merc_typecheck/inference/resolved_sort/enum.ResolvedSort.html#variant.TypeVar) it mentions becomes one fresh unification
variable, shared between all of that instantiation's occurrences, which is
what lets `in: S # List(S) -> Bool` mean "the same `S`" on both sides at one
particular call site. Zero candidates is an [`UndeclaredName`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.InferenceError.html#variant.UndeclaredName) error;
exactly one is bound directly, like a variable; more than one becomes a
[`Disjunction`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Disjunction) constraint, to be resolved later by the solver, not here.

There is no dedicated constraint kind for arithmetic operators — `+`, `-`,
`*`, `div`, `mod` and the rest are ordinary overloaded mappings declared in
`pos.mcrl2`/`nat.mcrl2`/`int.mcrl2`/`real.mcrl2`, so an application of one
goes through exactly this same `Disjunction` machinery.

### `merge_shared_subs`: from `Sub` groups to `Join`

Several `Sub` constraints can target the *same* shared free variable — the
two operands of `==`, the branches of an `if`, a set/bag element, an
equation's LHS and RHS. Solving them as independent, sequential `Sub`s is
order-sensitive: whichever source is solved first binds the shared variable
by equality, so if a finite-container source (a set literal, fixing `FSet`)
is solved before another source that only admits `Set`, the second source's
own `Sub` then fails and forces a fruitless re-exploration.
[`merge_shared_subs`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/fn.merge_shared_subs.html) runs once, right after generation, and groups every
`Sub` by the union-find root of its target: a group of two or more collapses
into a single [`Join`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Join), at the position of the group's last
member, computing the least common supersort of all sources in one step
instead. A disjunction's own candidate parameters are *distinct* fresh
variables per overload (the overload isn't committed to yet), so they are
never grouped this way.

## The solver

```
struct Solver:
    unifier, constraints, expr_sorts, base_names      -- inputs, shared for the whole search
    choices: [(ExprId, NameTarget)]                    -- disjunct picked per Disjunction, on the current branch
    measure: [u8]                                      -- measure components pushed on the current branch
    best: Option<Candidate>                             -- best leaf found so far
    default_sort: ResolvedSortId                        -- substituted for a hole still free at a leaf
```

[`Solver::solve`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/struct.Solver.html#method.solve) walks `constraints` left to right, discharging the one at
index $i$ and recursing into $i+1$. What makes this a **ranked** backtracking
search, rather than a plain one, is `measure`: a vector built up one
component at a time as choices are made along the current branch — earliest
generated constraint most significant — and compared **lexicographically**.
Reaching the end of the list is a leaf: a complete, self-consistent typing,
scored against the best leaf found on any branch so far.

Everything below this point is really one algorithm applied five times: pick
the next unsolved constraint, enumerate its *resolutions* (the ways it could
be satisfied), try them against the `Unifier`, and for each that applies,
push whatever it costs onto `measure` and recurse. The constraint kinds only
differ in what a "resolution" is and in which of two disciplines governs how
resolutions are tried:

- **exhaustive** — try every resolution, unconditionally, even once one has
  already succeeded. This is required wherever two *different* resolutions
  can reach leaves with an equal measure, since that tie must be reported as
  genuine ambiguity rather than resolved arbitrarily by whichever ran first.
  `Disjunction` and `Comprehension` both work this way.
- **first success** — try resolutions in ascending cost order and stop at
  the first whose continuation succeeds. This is safe wherever the
  resolutions are already ordered cheapest-first by construction: `Sub`
  (plain subsorting), `Lit`, and `Join` all work this way. Because the
  continuation recurses into the *rest* of the constraint list before
  returning, "first success" means first success of the entire remaining
  search, not just of this one constraint in isolation — a later constraint
  failing under a cheap resolution here still gets to retry once this one
  backtracks into a costlier resolution.

Both disciplines share the same snapshot/try/rollback shape: snapshot the
`Unifier`, attempt a resolution, and if it unifies, push its cost and
recurse; either way, roll back to the snapshot before trying the next
resolution, via [`Unifier::snapshot`/`rollback_to`](unification.md#snapshot-and-rollback).

```math algorithm
\begin{algorithmic}[1]
\Function{Solve}{$i$}
  \If{\Call{Dominated}{}}
    \State \Return \textsc{false} \Comment{branch-and-bound: this branch's measure prefix already loses}
  \EndIf
  \If{$i = n$}
    \State \Call{Leaf}{}
    \State \Return \textsc{true} \Comment{end of the list: score this solution}
  \EndIf
  \State \Return \Call{Discharge}{$\mathit{constraints}[i], i$} \Comment{constraint-specific, see below}
\EndFunction
\end{algorithmic}
```

### Branch-and-bound: `dominated`

```math algorithm
\begin{algorithmic}[1]
\Function{Dominated}{}
  \If{$\mathit{best} = \varnothing$}
    \State \Return \textsc{false}
  \EndIf
  \State \Return $\mathit{measure} > \mathit{best.measure}[0 \,.\,.\, \lvert \mathit{measure} \rvert]$ \Comment{component-wise, so-far prefix only}
\EndFunction
\end{algorithmic}
```

A `Disjunction`/`Comprehension` contributes no measure component of its own
(every alternative is tried regardless, so a tie is still detected as
ambiguity), so without this check an equation with several independent
overloaded operators would explore every *combination* to a full leaf even
after a strictly better solution is already known — exponential in the
number of disjunctions. The pruning is exact, not a heuristic: because
earlier measure components dominate the lexicographic order, a prefix that
is already strictly worse can never catch up, so this changes only how much
of the tree gets visited, never which typing wins.

### Exhaustive choice points: `solve_disjunction`, `solve_comprehension`

```math algorithm
\begin{algorithmic}[1]
\Function{Discharge}{Disjunction($d$), $i$}
  \State $\mathit{found} \gets \textsc{false}$
  \For{$(\mathit{target}, \mathit{sort}) \in d.\mathit{disjuncts}$}
    \State $s \gets \Call{Snapshot}{}$
    \If{\Call{Unify}{$d.\mathit{sort}, \mathit{sort}$}}
      \State $\mathit{choices}.\Call{Push}{(d.\mathit{expr}, \mathit{target})}$
      \State $\mathit{found} \gets \mathit{found} \lor \Call{Solve}{i+1}$
      \State $\mathit{choices}.\Call{Pop}{}$
    \EndIf
    \State \Call{RollbackTo}{$s$}
  \EndFor
  \State \Return $\mathit{found}$
\EndFunction
\end{algorithmic}
```

`solve_comprehension` has the same shape over exactly three fixed readings —
$(\textsc{Bool}, \textsc{Set})$, $(\textsc{Nat}, \textsc{Bag})$,
$(\textsc{Pos}, \textsc{Bag})$ — unifying both the body sort and the
comprehension node's own sort against each reading in turn, with no
`choices` entry to record. Both functions try **every** alternative
unconditionally (no early return on success): that is the exhaustive
discipline described above, and it's precisely what lets two alternatives
reaching equal-measure leaves both get recorded and detected as a tie by
`leaf`, rather than the first success silently shadowing the second.

### Subsorting: `solve_sub` / `solve_widening`

```math algorithm
\begin{algorithmic}[1]
\Function{Widen}{$\mathit{lhs}, \mathit{rhs}, i$}
  \State $s \gets \Call{Snapshot}{}$
  \If{\Call{Unify}{$\mathit{lhs}, \mathit{rhs}$}} \Comment{try equality first}
    \State push $0$ onto \textit{measure}
    \State $\mathit{found} \gets \Call{Solve}{i+1}$
    \State pop \textit{measure}
  \EndIf
  \State \Call{RollbackTo}{$s$}
  \If{$\mathit{found}$}
    \State \Return \textsc{true}
  \EndIf
  \State $\mathit{pairs} \gets \Call{StrictSuperSorts}{\mathit{lhs}} \times \{\mathit{rhs}\}$, \textbf{or else} $\{\mathit{lhs}\} \times \Call{StrictSubSorts}{\mathit{rhs}}$
  \If{neither side has an enumerable shape}
    \State \Return \textsc{false}
  \EndIf
  \For{$(\mathit{distance}, (\mathit{lhs}', \mathit{rhs}')) \in \mathit{pairs}$} \Comment{nearest widening first}
    \State $s \gets \Call{Snapshot}{}$
    \If{\Call{Unify}{$\mathit{lhs}', \mathit{rhs}'$}}
      \State push $1 + \mathit{distance}$ onto \textit{measure}
      \State $\mathit{found} \gets \Call{Solve}{i+1}$
      \State pop \textit{measure}
    \EndIf
    \State \Call{RollbackTo}{$s$}
    \If{$\mathit{found}$}
      \State \Return \textsc{true}
    \EndIf
  \EndFor
  \State \Return \textsc{false}
\EndFunction
\end{algorithmic}
```

`Widen` is shared by `solve_sub` (a plain `Sub` constraint, calling
`Widen(lhs, rhs, i)` directly as its `Discharge`) and, as a fallback, by the
`Join` path below. It is the concrete instance of the **first success**
discipline: equality if it works, otherwise the nearest strict widening that
works, stopping there — never comparing alternative widening distances
against each other directly. That is enough to guarantee the minimal upcast
wins, for the reason given above: distances are tried in ascending order,
and `Solve` recurses into the *rest* of the constraint list before `Widen`
returns, so a later constraint failing under a near widening still gets to
retry under a farther one — "first success" here means first success of the
whole remaining search, not just of this one constraint in isolation.

### Literals: `solve_lit`

A literal's sort is either already resolved (check its generality admits
the literal's kind — reject `Pos` for a literal that must be `Natural` like
`0` — and push that generality as the measure, with no choice involved), or
still a hole, in which case `Discharge` is again a **first success** search:
try each admissible number sort most-specific-first —
$[\textsc{Pos}, \textsc{Nat}, \textsc{Int}, \textsc{Real}]$ for a `Positive`
literal, $[\textsc{Nat}, \textsc{Int}, \textsc{Real}]$ for a `Natural` one —
unifying, pushing that sort's generality as the measure component,
recursing, and rolling back on failure. Same snapshot/try/rollback shape as
`Widen`, just over a fixed list instead of the lattice's neighbor relation.

### The lattice join: `solve_join` / `solve_join_seq`

```math algorithm
\begin{algorithmic}[1]
\Function{Discharge}{Join($j$), $i$}
  \State $\mathit{resolved} \gets [\Call{Resolve}{s} : s \in j.\mathit{sources}]$
  \If{some source in $\mathit{resolved}$ is unresolved}
    \State \Return \Call{JoinSeq}{$j.\mathit{sources}, j.\mathit{target}, 0, i$} \Comment{fallback}
  \EndIf
  \State $\mathit{lub} \gets \mathit{resolved}[0]$
  \For{$\mathit{next} \in \mathit{resolved}[1 \,.\,.\,]$}
    \If{$\mathit{lub} \sqcup \mathit{next}$ is undefined} \Comment{not joinable by the simple lattice}
      \State \Return \Call{JoinSeq}{$j.\mathit{sources}, j.\mathit{target}, 0, i$}
    \EndIf
    \State $\mathit{lub} \gets \mathit{lub} \sqcup \mathit{next}$
  \EndFor
  \If{some source in $\mathit{resolved}$ is not materializable into $\mathit{lub}$}
    \State \Return \Call{JoinSeq}{$j.\mathit{sources}, j.\mathit{target}, 0, i$} \Comment{lowering can't build this coercion yet}
  \EndIf
  \If{$\lnot \Call{Unify}{j.\mathit{target}, \mathit{lub}}$}
    \State \Return \textsc{false}
  \EndIf
  \For{$\mathit{source} \in \mathit{resolved}$}
    \State push $\Call{WideningDistance}{\mathit{source}, \mathit{lub}}$ onto \textit{measure} \Comment{one component per source, matching \Call{Widen}{}}
  \EndFor
  \State $\mathit{found} \gets \Call{Solve}{i+1}$
  \State pop all pushed components
  \State \Return $\mathit{found}$
\EndFunction
\end{algorithmic}
```

```math algorithm
\begin{algorithmic}[1]
\Function{JoinSeq}{$\mathit{sources}, \mathit{target}, k, i$} \Comment{the pre-merge, per-source behavior, as a fallback}
  \If{$k = \lvert \mathit{sources} \rvert$}
    \State \Return \Call{Solve}{i+1}
  \EndIf
  \State \Return \Call{Widen}{$\mathit{sources}[k], \mathit{target}, i'$} \Comment{$i'$ continues as \Call{JoinSeq}{$\mathit{sources}, \mathit{target}, k+1, i$}}
\EndFunction
\end{algorithmic}
```

The fast path is deterministic — it makes no choice at all, just computes a
lattice join and unifies once — and only fires when every source is already
fully resolved *and* pairwise joinable *and* the join's result is one
lowering can actually materialize (container-element covariance and
function contravariance are relations the lattice can compute but Phase 4
lowering cannot yet build coercions for). Otherwise it defers to
`solve_join_seq`, which is nothing but `Widen` applied once per source in
turn — the same **first success** discipline as a plain `Sub`, composed
sequentially — reproducing exactly the order-sensitive per-source widening
the pre-`merge_shared_subs` encoding used, so the rare underdetermined case
(e.g. joining two still-open empty containers) behaves identically to
before that optimization existed.

### Scoring and extracting: `leaf` / `extract`

```math algorithm
\begin{algorithmic}[1]
\Function{Leaf}{}
  \If{$\mathit{best} = \varnothing$ \textbf{or} $\mathit{measure} < \mathit{best.measure}$}
    \State $\mathit{best} \gets \Call{Extract}{}$ \Comment{strictly better}
  \ElsIf{$\mathit{measure} = \mathit{best.measure}$}
    \State $\mathit{best.duplicate} \gets \textsc{true}$ \Comment{tie: ambiguous}
  \EndIf
  \Comment{$\mathit{measure} > \mathit{best.measure}$ cannot occur here: \Call{Dominated}{} would already have pruned it}
\EndFunction
\end{algorithmic}
```

```math algorithm
\begin{algorithmic}[1]
\Function{Extract}{} \Comment{reads bindings before backtracking destroys them}
  \State $\mathit{sorts} \gets [\Call{ResolveOrDefault}{\mathit{node}, \mathit{default\_sort}} : \mathit{node} \in \mathit{expr\_sorts}]$
  \State $\mathit{names} \gets \mathit{base\_names} \cup \mathit{choices}$ \Comment{every Disjunction's committed NameTarget, overlaid}
  \State \Return $\mathit{Candidate}\{\mathit{measure}, \mathit{duplicate} \gets \textsc{false}, \mathit{typing} \gets (\mathit{sorts}, \mathit{names})\}$
\EndFunction
\end{algorithmic}
```

`extract` runs **before** the caller unwinds back through the `snapshot`s
that led to this leaf, since those bindings are exactly what it's reading.
Every free node still unbound at this point (a hole nothing ever
constrained, like the element sort of a never-observed empty container)
resolves to `default_sort` instead of `None` — see
[`Unifier::resolve_or_default`](unification.md#resolving-a-solved-node). That default is
computed once per equation, before solving starts, by
[`underdetermined_default_sort`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/fn.underdetermined_default_sort.html): ordinarily `Bool` — an arbitrary
but harmless choice, since a node that reaches this path is by definition
never observed by any other constraint — except when checking one Appendix-B
template's own equations with exactly one declared `type_var`, where
defaulting to `Bool` would be actively wrong: a bare literal like the `{}` in
`#({}) = @c0` has no `var`-declared occurrence to unify its element sort
against, so it would *always* solve to `Bool` regardless of which concrete
sort the template later gets instantiated for. Defaulting to the template's
own type variable instead keeps such a literal polymorphic through checking,
exactly like a declared occurrence would be, so specialization substitutes it
correctly.

## Worked example: an eagerly-bound argument pruning a disjunct

```mcrl2
map  f: Nat -> Nat;
     f: Int -> Int;
var  n: Nat;
eqn  f(n) = n;
```

Generation visits the argument `n` before the callee `f` (argument-before-
function ordering), binding `n`'s node directly to `Nat` — it's a declared
variable, not a disjunction. `f`'s occurrence then becomes a two-way
[`Disjunction`](https://mercorg.github.io/merc/merc_typecheck/inference/inference/enum.Constraint.html#variant.Disjunction), solved by the exhaustive `Discharge` above:

- **`f: Nat -> Nat`** — unifying the parameter against the argument node
  (already `Nat`) succeeds by equality; the `Sub` constraint linking them
  contributes measure `0`.
- **`f: Int -> Int`** — the argument is `Nat`, the parameter wants `Int`;
  equality fails, `Widen` falls through to `StrictSuperSorts(Nat)` =
  `[Int, Real]`, and the nearest, `Int`, succeeds at distance `1`.

Both branches reach a leaf — the call type-checks either way — but their
measures differ at that one component: `[…, 0, …]` beats `[…, 1, …]`, so
`Nat -> Nat` is the unique best solution and no `AmbiguousExpression` is
raised. This is the concrete mechanism behind the informal rule "the exact
overload wins over one that needs an up-cast": nothing in `unify` itself
prefers one branch over the other, it's `leaf`'s lexicographic comparison of
`measure` that does.
</content>
