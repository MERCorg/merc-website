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

## Group order

The same `used` groups applied in five orders: by first summand, by top from deep
to high (the order chaining uses), by top from high to deep, by bottom from high
to deep, and that last order reversed. Release `merc-lps explore --cached`, one
worker, reachability seconds, 16 GiB cgroup, single runs. All runs found the same
state counts.

Chaining:

| model | first summand | top, deep first | top, high first | bottom, high first | reversed |
|---|---:|---:|---:|---:|---:|
| Aravind BLRU | 20.0 | 18.5 | 23.5 | 23.2 | 20.3 |
| Lamport 3-bit | 142.0 | 142.6 | 206.2 | 150.7 | 143.1 |
| Dijkstra | 1.64 | 1.84 | 2.01 | 2.18 | 1.62 |
| 1394 | 2.54 | 2.51 | 2.56 | 2.54 | 2.52 |

Firing the deep groups first is the best order or within noise of it; firing the
high groups first is clearly the worst. For saturation only the order within one
level can differ. Median of three runs, wall seconds:

| model | first summand | bottom, high first | reversed |
|---|---:|---:|---:|
| Aravind BLRU | 4.5 | 5.7 | 5.4 |
| Dijkstra | 1.0 | 1.0 | 1.0 |

On a large industrial model with chaining, bottom-first reached 38,479 states
after 40 rounds against 9,807 in summand order; top-first was not measured there.
