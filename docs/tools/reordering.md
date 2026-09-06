# Reordering 

A variable ordering for linear process specifications (`.lps`) and parameterised
Boolean equation systems (`.pbes`) can be computed using the `merc-lps` or
`merc-pbes` tools with the `--reorder mince` option. These orderings are based
on heuristics, for now only the balanced hypergraph partition heuristic called
`MINCE` has been implemented. See the paper, for more details:

> Clemens Dubslaff, Nils Husung, Nikolai Käfer: Tailoring binary decision diagram compilation for feature models. J. Syst. Softw. 231: 112566 (2026)

For the hypergraph partition based on balanced min-cut heuristics, we use the
tool [KaHyPar](https://github.com/kahypar/kahypar), which can be built from
source using the instructions on their GitHub page.

After acquiring these prerequisites, the variable ordering can be computed using
the following command:

```bash
merc-pbes solve --reorder mince <file.pbes> --kahypar-path <path-to-kahypar> --kahypar-ini-path <path-to-kahypar-ini>
```

The `path-to-kahypar` will be `<repo>/build/kahypar/applications/` when built
Passing the ini file is only necessary in a developement build, and it should point to the location of the ini file, which is
`merc/crates/symbolic/data/kahypar.ini`.

The resulting order will be applied immediately, but also printed
to standard output, and can be passed directly using the `--reorder="<order>"`
option.