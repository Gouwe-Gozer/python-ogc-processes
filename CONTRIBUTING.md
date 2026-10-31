# Contributing

Keep changes focused and explain resulting behavior, validation and limitations.
Follow [development](docs/development.md) for setup, Ruff, Bandit, pytest/coverage,
configuration/OpenAPI checks and pre-commit. Pair dependency changes with the lockfile.

For a new operation, use the [Python process guide](docs/adding-a-process.md) and
[architecture](docs/architecture.md). Reuse input/result lifecycles and the
[exception catalogue](docs/errors.md); give each process its own contract.

Use the [OGC review guide](docs/validation.md#ogc-review-guide) when changing
schemas, execution, delivery or capability claims. Include meaningful operation/HTTP
tests and review baseline changes explicitly. Historical reports do not validate
new behavior.

Update the README for user-visible behavior and the relevant maintained `docs/`
page for technical details. Keep proposed work in the [roadmap](docs/roadmap.md),
with implemented and unimplemented capabilities clearly distinguished. Keep investigations and dated test diaries separate from maintained guidance.
