# The MERC Project

The goal of the `MERC` project is to provide a generic set of libraries and tools for (specification) language-agnostic model checking, written in the [Rust](https://rust-lang.org/) language. The name is an acronym for "[**m**CRL2](https://www.mcrl2.org/web/index.html) **e**xcept **R**eliable & **C**oncurrent", which should not be taken literally. Main development of the `merc` project takes place on [GitHub](https://github.com/MERCorg/merc).

We aim to demonstrate efficient and correct implementations using (safe) Rust. The main focus is on clean interfaces to allow the libraries to be reused as well. The toolset supports and is tested on all major platforms: Linux, macOS and Windows.

!!! note Announcement
    The first release `v1.0` of `MERC` has been published in December 2025, and is available to download on the Github [releases](https://github.com/MERCorg/merc/releases) page. The corresponding crates have also been published on [crates.io](https://crates.io/users/mlaveaux).

# Overview

Various tools have been implemented so far:

 - `merc-lts` implement various (signature-based) bisimulation algorithms for labelled transition systems in the mCRL2 binary [`.lts`](https://www.mcrl2.org/web/user_manual/tools/lts.html) format and the AUTomaton (or ALDEBARAN) [`.aut`](https://cadp.inria.fr/man/aut.html) format.
 - `merc-rewrite` allows rewriting of Rewrite Engine Competition specifications ([REC](https://doi.org/10.1007/978-3-030-17502-3_6)) using [Sabre](https://arxiv.org/abs/2202.08687) (Set Automaton Based Rewriting).
 - `merc-vpg` can be used to solve (variability) parity games in the [PGSolver](https://github.com/tcsprojects/pgsolver) `.pg` format, and a slightly extended variability parity game `.vpg` format. Furthermore, it can generate variability parity games for model checking modal mu-calculus on LTSs.
 - `merc-pbes` can identify symmetries in paramerised boolean equation systems [PBES](https://doi.org/10.1016%2Fj.tcs.2005.06.016), located in the `tools/mcrl2` workspace.
 - `merc-ltsgraph` is a GUI tool to visualize LTSs, located in the `tools/GUI` workspace.

Various crates are also published on [crates.io](https://crates.io/users/mlaveaux), see the `crates` directory for an overview.

