# Benchmarks

This section collects the measured results of `merc`: running times, node counts
and rewrite-step counts of particular builds on particular inputs. Unlike the
definitions and theorems on the rest of this site, these
figures change with the code, the compiler and the machine, so those pages state
the design and the reason for it, and link here for the numbers.

The figures were recorded by hand and are not generated from a benchmark run, so
they can lag behind the code. How to run the micro-benchmarks is described in
[Overview, Benchmarks](../contributing/general.md#benchmarks).

| page | measures |
|---|---|
| [Rewriting](rewriting.md) | the innermost and jitty rewriters against each other and against mCRL2, and the effect of individual design decisions |
| [Parsing](parsing.md) | parse times of process specifications with long chains of conditions |
| [Symbolic](symbolic.md) | node counts and times of saturation, and its garbage |
