# Contributing

Use focused changes and explain resulting behavior, validation and remaining
limitations in pull requests. Add or adapt meaningful tests for contract and
behavior changes. Keep dependency updates paired with their lockfile changes.

Run the existing Ruff, Bandit and pytest/coverage checks described in
[development](docs/development.md). Changes to process schemas, validation
baselines and deployment behavior should include enough evidence to review
the new contract. Do not use historical reports as evidence for a new service.

Follow the [pivot decision](docs/rasterio-pivot.md) and [roadmap](docs/roadmap.md)
toward Rasterio-backed processing of users' own rasters, with vector processes
added as needed. Use the [OGC review guide](docs/validation.md#ogc-review-guide)
when changing process descriptions, input routes, result formats or capability
claims; document remaining gaps alongside the evidence.
