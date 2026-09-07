```math_preamble

\usepackage{tikz}
\usetikzlibrary{babel,arrows.meta,positioning,calc}
\usepackage{tikz-qtree}
```
# Grammar-Ambiguity

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
\begin{scope}[local bounding box=parsedTreeA]
\Tree [.\textbf{Condition}
        [.\texttt{cond} [.\textsc{At} \texttt{a(1)} \textsc{true} ] ]
        [.\texttt{then} \texttt{delta} ] ]
\end{scope}
\node[font=\footnotesize, below=0.5cm of parsedTreeA.south] {as parsed};
\begin{scope}[shift={($(parsedTreeA.east)+(1.5cm,0)$)}, local bounding box=recoveredTreeA]
\Tree [.\textsc{Sequence}
        \texttt{a(1)}
        [.\textbf{Condition} [.\texttt{cond} \textsc{true} ] [.\texttt{then} \texttt{delta} ] ] ]
\end{scope}
\node[font=\footnotesize, below=0.5cm of recoveredTreeA.south] {as recovered};
\end{tikzpicture}
```

</div>

`disambiguate` recognizes `a` as a declared action name, peels it off the
`At` chain, and rebuilds the `Sequence`/`Condition` shape on the right.

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
\begin{scope}[local bounding box=parsedTreeB]
\Tree [.\textbf{Condition}
        [.\texttt{cond} \textsc{true} ]
        [.\texttt{then} [.\textbf{Condition}
                           [.\texttt{cond} [.\textsc{Add} \texttt{a(1)} \textsc{false} ] ]
                           [.\texttt{then} \texttt{b(2)} ] ] ] ]
\end{scope}
\node[font=\footnotesize, below=0.5cm of parsedTreeB.south] {as parsed};
\begin{scope}[xshift=9cm, local bounding box=recoveredTreeB]
\Tree [.\textsc{Choice}
        [.\textbf{Condition} [.\texttt{cond} \textsc{true} ] [.\texttt{then} \texttt{a(1)} ] ]
        [.\textbf{Condition} [.\texttt{cond} \textsc{false} ] [.\texttt{then} \texttt{b(2)} ] ] ]
\end{scope}
\node[font=\footnotesize, below=0.5cm of recoveredTreeB.south] {as recovered};
\end{tikzpicture}
```

</div>

Note the misparse nests one `Condition` inside the other's `then`, not a
top-level `Binary { op: Add, .. }` sitting beside it — `disambiguate` has to
walk into an as-parsed `then` looking for exactly this shape (`take_swallow`
in `crate::process::disambiguation`) before it can split it back into
sibling `Choice` branches. `P || cond -> Q` (parallel composition guarding a
condition) is the same bug with `Disj`/`Parallel` in place of `Add`/`Choice`.
A single-action
`hide`/`block`/`allow` application (`hide({a}, P)`, ordinary function-call
syntax) can also appear as the swallowed operand and is recovered the same
way, re-attaching its action set to the rebuilt `Hide`/`Block`/`Allow` node.

Before type checking runs, `crate::process::disambiguation` walks the
specification and rewrites every misparsed `Condition` back into the
`Sequence`/`Choice`/`Parallel`/`Action`/`Hide`/`Block`/`Allow` shape it should
have parsed as. This needs only the declared action/process *names*, matching
how mCRL2 itself resolves the same ambiguity before its own type checking
runs. Because the
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

See also [Precedence: Pest (merc) vs. dparser (mCRL2)](precedence.md) for a
different, unrelated class of grammar disagreement between the two parsers —
this page is about a token-overload ambiguity `merc_syntax` resolves itself
after parsing; that one is about the two parsers disagreeing on what a single
unambiguous-looking expression even means.
