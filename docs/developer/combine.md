# Combining LTSs

 > ⚠️ **important** This documentation is WIP.
 
The original version of the tool `ltscombine` in the mCRL2 toolset was implemented by Willem Rietdijk as part of his master's thesis. The work is inspired by the composition of networks of LTSs in CADP.

Let $L_0, \ldots, L_n$ be labelled transition systems such that $L_i = (S_i, s^0_i, \Sigma_i, \rightarrow_i)$, where

- $S_i$ denotes the set of states,
- $s^0_i$ is the initial state,
- $\Sigma_i$ is the alphabet of LTS $i$, and
- $\rightarrow_i \subseteq S_i \times (\Sigma_i \cup \{\tau\}) \times S_i$ is the transition relation.

We assume for $0 \leq i < j \leq n$ that $S_i \cap S_j = \emptyset$, i.e. the sets of states are disjoint.

The goal of `ltscombine` is to compute the LTS $\tau_I \nabla_V \Gamma_C (L_0 \parallel \cdots \parallel L_n)$.

We first specify the operations hide ($\tau$), allow ($\nabla$) and communication ($\Gamma$) on LTSs; the definitions are adapted from Rietdijk's thesis.

---

**Definition** (Hide)

Let $L = (S, s^0, \Sigma, \rightarrow)$ be an LTS, and $I$ a set of action names. Then $\tau_I(L)$ is the LTS $L' = (S, s^0, \Sigma', \rightarrow')$ where

- $\Sigma' = \{\tau_I(\alpha) \mid \alpha \in \Sigma\}$, and
- $\rightarrow' = \{(s,\ \tau_I(\alpha),\ s') \mid s \xrightarrow{\alpha} s'\}$

where $\tau_I(\tau) = \tau$ and $\tau_I(a|\alpha) = \tau_I(\alpha)$ if $a \in I$, and $a|\tau_I(\alpha)$ otherwise.

---

**Definition** (Allow)

Let $L = (S, s^0, \Sigma, \rightarrow)$ be an LTS, and $V$ a set of multi-action names. Then $\nabla_V(L)$ is the LTS $L' = (S', s^0, \Sigma', \rightarrow')$ where

- $S' = \{s \in S \mid s^0 \xrightarrow{\sigma}^* s\}$,
- $\Sigma' = \Sigma \cap V$, and
- $\rightarrow' = \{(s,\ \alpha,\ s') \mid s \xrightarrow{\alpha} s' \land \alpha \in V \cup \{\tau\}\}$

Note that the definition restricts $S'$ to the reachable states, and $\alpha$ removes the arguments from the actions in $\alpha$.

---

**Definition** (Communication)

Let $L = (S, s^0, \Sigma, \rightarrow)$ be an LTS, and $C$ a set of communication expressions. Then $\Gamma_C(L)$ is the LTS $L' = (S, s^0, \Sigma', \rightarrow')$ where

- $\Sigma' = \{\gamma_C(\alpha) \mid \alpha \in \Sigma\}$, and
- $\rightarrow' = \{(s,\ \gamma_C(\alpha),\ s') \mid s \xrightarrow{\alpha} s'\}$

where $\gamma_C$ is the communication operator over closed terms as defined below.

---

We now give a high-level description of the algorithm.

**Definition** (Communication operator)

Let $C$ be a set of communications of the form $a_1 | \cdots | a_n \rightarrow c$, with $n > 1$, and $a_i$ and $c$ action names. The function $\gamma_C$ applies the communications to a multiaction $\alpha$. This is defined as follows:

$$\gamma_\emptyset(\alpha) = \alpha$$

$$\gamma_{C_1 \cup C_2}(\alpha) = \gamma_{C_1}(\gamma_{C_2}(\alpha))$$

$$\gamma_{\{a_1|\cdots|a_n \rightarrow b\}}(\alpha) = \begin{cases} b(d)\ |\ \gamma_{a_1|\cdots|a_n \rightarrow b}(\alpha \setminus (a_1(d)|\cdots|a_n(d))) & \text{if } a_1(d)|\cdots|a_n(d) \sqsubseteq \alpha \text{ for some } d \\ \alpha & \text{otherwise} \end{cases}$$

---

## Algorithm

$$\textbf{Compose}(I,\ A,\ C,\ \{L_0, \ldots, L_n\})$$

**Input:** a set of actions $I$ to be hidden, a set of multi-action names $A$ to be allowed, a set of communication expressions $C$, a set of LTSs $\{L_0, \ldots, L_n\}$

**Output:** The LTS $\tau_I \nabla_A \Gamma_C (L_0 \parallel \cdots \parallel L_n)$

$$
\begin{array}{l}
\textbf{algorithm } \text{Compose}(I, A, C, \{L_0, \ldots, L_n\}) \\
\hline
\end{array}
$$

```latex
\begin{algorithm}
\caption{Compose$(I, A, C, \{L_0, \ldots, L_n\})$}
\begin{algorithmic}[1]
\State $s^0 \gets (s^0_0, \ldots, s^0_n)$
\State $\textit{todo} \gets \{s^0\}$
\State $S \gets \{s^0\}$
\State ${\rightarrow} \gets \emptyset$
\While{$\textit{todo} \neq \emptyset$}
    \State Pick $(s_0, \ldots, s_n)$ from $\textit{todo}$
    \State $\textit{todo} \gets \textit{todo} \setminus \{(s_0, \ldots, s_n)\}$
    \ForAll{$J \subseteq \{0,\ldots,n\},\ \{j_0,\ldots,j_m\} \in J$ such that $s_{j_0} \xrightarrow{\alpha_{j_0}} t_{j_0},\ \ldots,\ s_{j_m} \xrightarrow{\alpha_{j_m}} t_{j_m}$}
        \State $\alpha \gets \alpha_0 | \cdots | \alpha_m$
        \State $t \gets (t_0, \ldots, t_m)$
        \State $\alpha \gets \gamma_C(\alpha)$
        \If{$\alpha \in A \cup \{\tau\}$}
            \State $\alpha \gets \tau_I(\alpha)$
            \State ${\rightarrow} \gets {\rightarrow} \cup \{(s, \alpha, t)\}$
            \If{$t \notin S$}
                \State $\textit{todo} \gets \textit{todo} \cup \{t\}$
                \State $S \gets S \cup \{t\}$
            \EndIf
        \EndIf
    \EndFor
\EndWhile
\end{algorithmic}
\end{algorithm}
```