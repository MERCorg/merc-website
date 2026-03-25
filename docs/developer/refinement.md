```math_preamble
\usepackage{algpseudocode}

\newcommand{\refinesnew}[1]{\ensuremath{\textsc{refines-#1}_\textsc{new}}}
\newcommand{\antichain}{\mathit{antichain}}
\newcommand{\discovered}{\mathit{discovered}}
\newcommand{\impl}{\mathit{impl}}
\newcommand{\spec}{\mathit{spec}}
\newcommand{\working}{\mathit{working}}
\newcommand{\states}{\mathit{S}}

\newcommand{\transition}[1]{\xrightarrow{#1}\!\!\!\!\!\!\rightarrow}
\newcommand{\weaktransition}[1]{\overset{#1}{\Longrightarrow}}

\newcommand{\emptytrace}{\epsilon}
```

 > ⚠️ **important** This documentation is WIP.

# Refinement

The antichain based refinement checking algorithms implemented in `merc-lts` are based on the following paper:

 >  Maurice Laveaux, Jan Friso Groote and Tim A.C. Willemse. "Correct and efficient antichain algorithms for refinement checking". Logical Methods in Computer Science, 2021. [DOI](https://doi.org/10.23638/LMCS-17(1:8)2021).

The pseudocode for the weak trace refinement checking algorithm is shown below.

```math

\begin{algorithmic}
  \Procedure{Weak-Trace}{$s_1, s_2$}
  \State {let $\working$ be a stack containing the pair $(s_1, \{s \in \states_2 \mid s_2 \weaktransition{\emptytrace}_2 s\})$ }
  \State {let $\discovered \gets \{(s_1, \{s \in \states_2 \mid s_2 \weaktransition{\emptytrace}_2 s\})\}$}
  \While {$\working \neq \emptyset$}
    \State {pop ($\impl,\spec$) from $\working$}
    \For {$\impl \transition{a}_1 \impl'$}
      \If {$a = \tau$}
        \State {$\spec' \gets \spec$}
      \Else
        \State {$\spec' \gets \{s' \in \states_2 \mid \exists s \in \spec : s \weaktransition{a}_2 s'\}$}		
      \EndIf
      \If {$\spec' = \emptyset$}
        \Return false
      \EndIf
      \If {$(\impl', \spec') \not\in \discovered$}
        \State {$\discovered \gets \discovered \cup \{ (\impl', \spec')\}$}
        \State {push $(\impl', \spec')$ into $\working$}
      \EndIf	
    \EndFor
  \EndWhile
  \Return true
  \EndProcedure
\end{algorithmic}

```