# Overview

The goal of the `MERC` project is to provide a generic set of libraries and tools for (specification language-agnostic) model checking, written in the Rust language. The name is an acronym for "[**m**CRL2](https://www.mcrl2.org/web/index.html) **e**xcept **R**eliable & **C**oncurrent", which should not be taken literally. Main development of the `merc` project takes place on [GitHub](https://github.com/MERCorg/merc).

# Structure

The `crates` directory contains the main Rust crates of the project. However, there are also some C++ components in the `tools/mcrl2` directory, which are used for interoperability with existing `mCRL2` tools and libraries. They are a separate workspace, because they depend on C++ libraries and require various additional build steps and dependencies.


