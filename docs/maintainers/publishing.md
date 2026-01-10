
## Versioning scheme

We use [Semantic Versioning](https://semver.org/) for versioning the `MERC`
project, but for the time being we are not so concerned with breaking changes
since the project is still in its early stages.

## Publishing Crates

The Cargo
[documentation](https://doc.rust-lang.org/cargo/reference/publishing.html) for
publishing crates on [crates.io](https://crates.io/) provides a good starting
point for understanding the publishing process. Below are some additional
guidelines specific to the `MERC` project. 

Every crate should contain a `README.md` file in its root directory, which will
be displayed on the crate's page on `crates.io`. This file should provide an
overview of the crate, its purpose, and basic usage instructions. Furthermore,
ensure that the `Cargo.toml` file is properly filled out with relevant metadata,
including the crate's name, version, authors, description, license, and
repository URL. Before publishing a crate, it is essential to run tests and
ensure that the crate builds successfully.

Internal crates that are not intended for public use should have the following
note in the `README.md` file indicating that they should not be relied upon.
They must still be published because otherwise crates that depend on them cannot
be published.

 > ⚠️ **important** This is an internal crate and is not intended for public use.