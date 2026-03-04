# Overview

This document describes general development guidelines and practices for the
`merc` project.

## Formatting

All code should be formatted using `cargo +nightly fmt --all` to ensure a consistent coding style across the entire codebase. Furthermore, we run `cargo clippy` to catch common mistakes and enforce additional lints. This can be executed using `cargo clippy`.

## Benchmarks

Micro-benchmarks can be executed using `cargo bench`. Additionally, we can also install `cargo-criterion` and run `cargo criterion` instead to keep track of more information such as changes over time.

### Profiling

Tools built using the `release` compilation profile automatically contain all the debugging information required for profiling with external tools,  such as `Intel VTune` or `perf`.

Another useful technique for profiling is to generate a so-called `flamegraph`, which essentially takes the output of `perf` and produces a callgraph of time spent over time. These can be generated using the [flamegraph-rs](https://github.com/flamegraph-rs/flamegraph) tool, which can be acquired using `cargo install flamegraph`. Note that it relies on either `perf` or `dtrace` and as such is only supported on Linux and MacOS.

Finally, in performance critical situations it can be useful to view the generated assembly, which can be achieved with the `cargo asm --rust --simplify -p <package> [--lib] <path-to-function>` that can be obtained by `cargo install cargo-show-asm`.

## Debug Information

For `dev` builds we split debug information using `split-debuginfo="packed"`,
which seems to speed up linking time and the resulting binaries are not
distributed anyway. For `release` builds we enable `debug = "line-tables-only"`
to enable line and function information in backtraces. In the `mcrl2` tools we
do not split debug info since `cpptrace` cannot seem to find it, and this breaks
stack traces in the `C++` code.