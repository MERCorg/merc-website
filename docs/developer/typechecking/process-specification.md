```math_preamble

\usepackage{tikz}
\usetikzlibrary{babel,arrows.meta,positioning}
\usepackage{tikz-qtree}
```
# Process Specification

`DataSpecification` only ever covers the data language. `ProcessSpecification`,
built on top of it, type checks a full `UntypedProcessSpecification`:
`ProcessSpecification::from_untyped` first type checks the embedded [data
specification](data-specification.md) exactly as
`DataSpecification::from_untyped_with` does, then resolves every `act`
argument sort and `glob`/`proc` parameter sort, and finally walks every `proc`
body and `init` — action and process-instantiation arguments against their
declared sorts (with overload resolution where a name is declared more than
once), `sum`/`dist`-bound variables in scope for the subtree they bind,
conditions against `Bool`, and time bounds/`dist` weights against `Real`.
There is no lower-level entry point that type checks a process body without
first running the reparse pass below — every path goes through
`from_untyped`. Errors are reported as `ProcessError`, a superset of
`WellTypedError`/`InferenceError`. Communication sort-compatibility is not
checked yet.

`ProcessSpecification::typing_info` exposes the same [span-keyed
`TypingInfo`](lsp.md) `DataSpecification` does, merged over every checked
process-body expression (action arguments, process-instantiation arguments,
conditions, time bounds, `dist` weights) — computed once during the
construction walk above, so reading it back afterwards is a cheap clone
rather than a second pass.

## The `.`/`+`/`||` grammar-ambiguity reparse pass

mCRL2's concrete syntax overloads tokens between the process algebra and the
data language — most notably `.` (process sequential composition vs. the data
"at"/indexing operator), `+` (process choice vs. data addition), and `||`
(process parallel composition vs. data disjunction). Disambiguating the
readings needs semantic information a context-free grammar doesn't have (the
grammar alone can't tell a declared action `a(1)` from a data application),
so `merc_syntax`'s grammar always takes the greedier data-expression reading.
In every case the misparse lands in the same place — a `Condition` node's
`condition` field, the one `DataExpr` slot in the process grammar with no
delimiter (no brackets, no `[...]`) bounding how far it extends, so the
parser happily keeps consuming `.`/`+`/`||` as data operators straight past
the point where the concrete syntax actually meant to hand control back to
the process algebra.

The `.` case: `a(1) . true -> delta` should parse as an unconditional action
step `a(1)` followed by a guarded `delta`, but `a(1) . true` reads just as
well as one data expression (`.` as the "at" operator), so that's the
reading the grammar commits to:

<div align="center">

```math

\begin{tikzpicture}
\tikzset{
  every tree node/.style={align=center, font=\footnotesize, draw, rounded corners=2pt, inner sep=3pt},
  edge from parent/.style={draw, -{Latex[length=1.8mm]}},
  level distance=1.2cm,
  sibling distance=0.9cm,
}
\begin{scope}
\Tree [.\textbf{Condition}
        [.\texttt{cond} [.\textsc{At} \texttt{a(1)} \textsc{true} ] ]
        [.\texttt{then} \texttt{delta} ] ]
\node[font=\footnotesize, below=0.5cm of current bounding box.south] {as parsed};
\end{scope}
\begin{scope}[xshift=5.2cm]
\Tree [.\textsc{Sequence}
        \texttt{a(1)}
        [.\textbf{Condition} [.\texttt{cond} \textsc{true} ] [.\texttt{then} \texttt{delta} ] ] ]
\node[font=\footnotesize, below=0.5cm of current bounding box.south] {as recovered};
\end{scope}
\end{tikzpicture}
```

</div>

`reparse` recognizes `a` as a declared action name, peels it off the `At`
chain, and rebuilds the `Sequence`/`Condition` shape on the right.

The `+`/`||` case is the same swallow one level up, and it compounds: `(true)
-> a(1) + (false) -> b(2)` should be two guarded choice branches, but the
parser folds the second guard straight into the first clause's `then`,
because `a(1) + (false)` is itself just as valid a data expression (`+` as
addition) as the two `Condition`s the concrete syntax intended:

<div align="center">

```math

\begin{tikzpicture}
\tikzset{
  every tree node/.style={align=center, font=\footnotesize, draw, rounded corners=2pt, inner sep=3pt},
  edge from parent/.style={draw, -{Latex[length=1.8mm]}},
  level distance=1.2cm,
  sibling distance=0.9cm,
}
\begin{scope}
\Tree [.\textbf{Condition}
        [.\texttt{cond} \textsc{true} ]
        [.\texttt{then} [.\textbf{Condition}
                           [.\texttt{cond} [.\textsc{Add} \texttt{a(1)} \textsc{false} ] ]
                           [.\texttt{then} \texttt{b(2)} ] ] ] ]
\node[font=\footnotesize, below=0.5cm of current bounding box.south] {as parsed};
\end{scope}
\begin{scope}[xshift=6cm]
\Tree [.\textsc{Choice}
        [.\textbf{Condition} [.\texttt{cond} \textsc{true} ] [.\texttt{then} \texttt{a(1)} ] ]
        [.\textbf{Condition} [.\texttt{cond} \textsc{false} ] [.\texttt{then} \texttt{b(2)} ] ] ]
\node[font=\footnotesize, below=0.5cm of current bounding box.south] {as recovered};
\end{scope}
\end{tikzpicture}
```

</div>

Note the misparse nests one `Condition` inside the other's `then`, not a
top-level `Binary { op: Add, .. }` sitting beside it — `reparse` has to walk
into an as-parsed `then` looking for exactly this shape (`take_swallow` in
`crate::process::reparse`) before it can split it back into sibling `Choice`
branches. `P || cond -> Q` (parallel composition guarding a condition) is the
same bug with `Disj`/`Parallel` in place of `Add`/`Choice`. A single-action
`hide`/`block`/`allow` application (`hide({a}, P)`, ordinary function-call
syntax) can also appear as the swallowed operand and is recovered the same
way, re-attaching its action set to the rebuilt `Hide`/`Block`/`Allow` node.

Before type checking runs, `crate::process::reparse` walks the specification and
rewrites every misparsed `Condition` back into the `Sequence`/`Choice`/
`Parallel`/`Action`/`Hide`/`Block`/`Allow` shape it should have parsed as. This
needs only the declared action/process *names*, matching how mCRL2 itself
resolves the same ambiguity before its own type checking runs. Because the
pass runs unconditionally first, the process-body walk never needs
error-driven recovery of its own — every `Condition` it sees is already
correctly shaped.

**Known limitation.** `||_` (`LeftMerge`) has no data-operator equivalent in
the grammar at all, so it can't reach this swallow through the same mechanism.
`comm`/`rename` use `from -> to` pairs inside their set argument, and `->`
isn't valid `DataExpr` syntax, so `comm` (and a multi-action `allow` entry,
`a|b`) fail to parse in the ambiguous position rather than being silently
misparsed — `rename` happens to already parse correctly there (the malformed
`DataExpr` attempt backs out, falling back to its own dedicated grammar rule)
with nothing to fix.

## A second, unrelated ambiguity: action vs. process instantiation

`name(args)` is ambiguous in a completely different way from the swallow
above, and `reparse` does not — and cannot — resolve it. mCRL2's grammar uses
one production, `Action`, for *both* an action instance and a positional
process instantiation; the parser hands out `ProcessExprKind::Action` for
either without knowing (or caring) which:

```rust
Rule::Action => {
    let action = Mcrl2Parser::Action(Node::new(primary))?;

    Ok(ProcessExprKind::Action(action.id, action.args).spanned(span))
}
```

`reparse` only ever asks "is this name declared as *either* an action or a
process" (see its `Names` set) to recognize process content while
un-swallowing a `Condition` — it never needs to know, and never determines,
*which* of the two `name` refers to. So every `Action(name, args)` node,
reparsed or not, still carries this ambiguity into type checking.

Two things resolve it there, in `crate::process::process_specification` and
`crate::process::check`:

1. **Declaration time.** `DeclarationTables::build` rejects a specification
   that declares the same name as both an action and a process outright
   (`ProcessError::ActionAndProcessConflict`) — such a name would make every
   use of `Action(name, args)` permanently ambiguous between the two tables,
   with no way for a later argument-sort check to break the tie. This means
   that by the time `check_action_or_process` runs, at most one of
   `actions_by_name`/`processes_by_name` ever has an entry for a given name;
   the two tables are mutually exclusive by construction, not by anything
   the check walk does itself.

2. **Check time.** Within whichever single table actually declares `name`,
   the name can still be legitimately *overloaded* — mCRL2 allows multiple
   `act`/`proc` declarations sharing a name, distinguished by argument sort
   or arity (mirroring `abp.mcrl2`'s `s3,r3,c3: D # Bool; s3,r3,c3: Error;`
   and `abp_bw.mcrl2`'s `S`, `S(b:Bit)`, `S(d:D,b:Bit)`). `check_action_or_process`
   collects every arity-matching candidate across both tables (a no-op chain
   on the side with no entry, per point 1), type checks each candidate's
   arguments against its own declared domain, and requires *exactly one* to
   succeed — zero is an undeclared name, more than one is a genuine ambiguity
   the declarations themselves didn't rule out (e.g. `act c: Nat; act c:
   Int;` called as `c(1)`: `Nat <= Int` widens either way, so a bare `Nat`
   argument doesn't disambiguate).

Resolving an overload needs the argument expressions' *sorts*, which only
exist once type checking is underway — no amount of syntactic
reparsing beforehand could move this check earlier.

The single winning candidate identified this way is also where `name`'s own
go-to-definition span is filled in — see [LSP support](lsp.md#action-and-process-instantiation-names-resolved-by-the-checker-not-the-pre-pass).
