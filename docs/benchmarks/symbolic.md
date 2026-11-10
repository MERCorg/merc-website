# Symbolic benchmarks

Measurements of [saturation](../model-checking/symbolic/saturation.md) on decision
diagrams.

## Peak nodes

On the pregenerated `anderson.4` fixture, `Saturation` peaks at about 13.5k nodes
in the manager against about 134k for `BreadthFirst`.

## Accumulator against node

Saturating the `anderson.6` example with the
[accumulator](../model-checking/symbolic/saturation.md#doing-it-without-mutating-nodes)
against the node-based version, which does the same number of firings and merges
(about 2.3 to 2.5 million):

| | accumulator | node as accumulator |
|---|---:|---:|
| nodes in the manager after saturating (the result has 49,037) | 0.67M | 2.60M |
| `Saturate` bodies (cache misses) | 153k | 787k |
| merge = union on a node, nodes created | – | 1.32M |
| merge = union on a continuation, nodes created | 0.37M | – |
| `head ∪ tail` unions, nodes created | – | 0.60M |
| time | about 2 s | about 4 s |

About 85% of the merges change nothing. The node-based version computes
`head ∪ tail` 338k times, which is a quarter of everything that it builds.

## Garbage

On the `anderson.6` example the result has 49,037 nodes, while saturating it
creates about 0.67 million, more than 90% of which are
[garbage](../model-checking/symbolic/saturation.md#memory-and-garbage-collection).

With oxidd's `manager-pointer` backend, which never collects garbage, a large
industrial model took hours for individual rounds, with the operation counts of
those rounds only a few times those of the fast ones. With the default
`manager-index` backend the same rounds took minutes, with identical state
counts. That model needed a few hundred million live nodes at its peak.
