

This is a testing file for math: $$\sum_{i}^{N} i$$, and pseudocode:

```pdflatex

\begin{algorithm}[ht]
  \footnotesize
  \caption{The weak trace inclusion checking algorithm.
  Upon termination, $\textsc{Weak-Trace}{(s_1, s_2)}$ returns \emph{true} if $s_1 \refinedbytrace s_2$, and \emph{false} if $s_1 \not\refinedbytrace s_2$, where $\lts_i = (\states_i, \init_i, \transitions_i)$ and $s_i \in \states_i$.}
  \label{alg:trace_inclusion}
  \begin{algorithmic}[1]
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
\end{algorithm}

```