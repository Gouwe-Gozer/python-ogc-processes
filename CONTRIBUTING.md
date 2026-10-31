# Contributing

Keep changes focused and explain resulting behavior, validation and limitations.
Follow [development](docs/development.md) for setup, Ruff, Bandit, pytest/coverage,
configuration/OpenAPI checks and pre-commit. Pair dependency changes with the lockfile.

To integrate your own Python function, start with [adding a process](docs/adding-a-process.md):
choose an in-repository module or external package, define its contract, register
the wrapper and install it in both API and worker. Check [resource configuration](docs/release-image.md#resource-configuration)
before choosing workload bounds. Reuse relevant input/result helpers and the
[exception catalogue](docs/errors.md). Detailed boundaries remain in [architecture](docs/architecture.md).

Use the [OGC review guide](docs/validation.md#ogc-review-guide) when changing
schemas, execution, delivery or capability claims. Include meaningful operation/HTTP
tests and review baseline changes explicitly. Historical reports do not validate
new behavior.

Update the README for user-visible behavior and the relevant maintained `docs/`
page for technical details. Keep proposed work in the [roadmap](docs/roadmap.md),
with implemented and unimplemented capabilities clearly distinguished. Keep
investigations and dated test diaries separate from maintained guidance. Preserve
useful technical knowledge publicly; archive unique historical/internal material
before removing it, without public links to private files.
