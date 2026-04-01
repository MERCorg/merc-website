# Variable Ordering

A variable ordering for linear process specifications (`.lps`) and parameterised
Boolean equation systems (`.pbes`) can be computed using the `merc-sym` tool
with the `reorder` option. These ordering are based on heuristics, for now only
the balanced hypergraph partition heuristic called `MINCE` has been implemented.
See the paper, for more details:

> Clemens Dubslaff, Nils Husung, Nikolai Käfer: Tailoring binary decision diagram compilation for feature models. J. Syst. Softw. 231: 112566 (2026)

For the hypergraph partition based on balanced min-cut heuristics, we use the
tool [KaHyPar](https://github.com/kahypar/kahypar), which can be built from
source using the instructions on their GitHub page.

We also use the tools `lpsreach` and `pbessolvesymbolic` from the
[mCRL2](https://www.mcrl2.org/) toolset, which can be installed using the
following the instructions on their website, to obtain the so-called dependency
graph for the `.lps` or `.pbes` file respectively.

After acquiring these prerequisites, the variable ordering can be computed using the following command:

```bash
merc-sym reorder <file.lps> --kahypar-path <path-to-kahypar> --mcrl2-path <path-to-mcrl2>
```

The `path-to-kahypar` will be `<repo>/build/kahypar/applications/` when built
from source, and the `path-to-mcrl2` will be `<repo>/build/stage/bin/` when
built from source. The resulting order will be printed to standard output, and
can be passed to the corresponding mCRL2 tools using the `--reorder="<order>"`
option.