# Parsing benchmarks

Measurements of the parser in
[`merc_syntax`](https://mercorg.github.io/merc/merc_syntax/index.html) on process
specifications with long chains of conditions. The causes and the workaround are
described in [Parsing conditions](../language/parsing/performance.md).

## Before marking conditions

Chains of *n* bare conditions, measured with every condition already correctly
identified, which isolates the
[second blow-up](../language/parsing/performance.md#the-second-independent-blow-up)
from the first:

| *n* | result |
|---:|---|
| 10 | 165 ms |
| 20 | does not finish in 3 s |
| 640 | overflows the stack |

Neither `MLV.mcrl2` nor `garage-ver.mcrl2` finished parsing, while the reference
mCRL2 toolset parses and linearizes both with `mcrl22lps` in under a second.

## After marking conditions

Parse times through `UntypedProcessSpecification::parse` (debug build), with the
[markers](../language/parsing/performance.md#the-workaround-marking-conditions)
in place:

| input | time |
|---|---:|
| `MLV.mcrl2` | 81 ms |
| `garage-ver.mcrl2` | 139 ms |
| *n* = 640 chain of bare conditions | 130 ms |
| *n* = 1280 | 331 ms |
| *n* = 2560 | 692 ms |
