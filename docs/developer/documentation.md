
Although it is never clear what is the best way to document a codebase, we have
some general guidelines that we try to follow in the `merc` project. Ideally, we
want the documentation close to the place where it is relevant, so no big UML
diagrams that have no relation to the source of truth, i.e., the code.

## Code

All code should contain documentation explaining the pre and post conditions of
the functions in the code, in the form of `rustdoc` comments. These comments can
use basic Markdown for formatting, and refer to other items in the codebase
using intra-doc links. Examples should be denoted as ```rust` code blocks, such
that they are tested as part of `rustdoc` tests.

## Crates

Each crate should contain a `README.md` file in its root directory that explains
the basic usage of the crate, and explains its overall purpose. This file can
also contain basic overall architecture of the crate, and should link to
relevant papers that the techniques in the crate are based on.

## Tools

For tools the documentation should focus on the usage of the tool, i.e., provide
more general text about what worksflows the tools are part of, and general flags
that should be used in the tool. 

