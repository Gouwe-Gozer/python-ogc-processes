# Development instructions

This repository implements `geo-processes`, a Rasterio/GDAL-backed OGC API –
Processes service built on pygeoapi. Code, configuration and tests define current
behavior. Use [development](docs/development.md), [architecture](docs/architecture.md)
and [validation](docs/validation.md) for maintained guidance.
`CODEX_HANDOVER.md` is historical planning material, not an active task plan.

## Environment and workflow

- Use user-installed `uv` and a project-local `.venv`: `uv sync --locked --all-groups`,
  then `uv run ...`. Do not install project packages into system Python.
- Inspect `pyproject.toml`, `uv.lock` and `.python-version` before changing Python
  or dependencies. Commit intentional dependency and lockfile updates together.
- Never use `sudo`, `apt`, global `pip` or `--break-system-packages`. Ask before
  modifying files outside this repository. Keep `.venv/` and generated data out
  of version control.
- Follow the user's branch and commit instructions. Do not commit, push or
  publish unless requested. Preserve existing work and MIT copyright/licence notices.

## Implementation

- Keep additions operation-specific: independent OGC processors/contracts and
  small Python/Rasterio adapters. See [adding a process](docs/adding-a-process.md).
- Reuse input validation, staging, result storage and synchronous execution.
  Shared infrastructure must preserve per-operation output IDs, formats and
  transmission modes; do not assume one JSON output or value-only delivery.
- Do not add a generalized engine plugin system or asynchronous job infrastructure
  as incidental work. Add vector libraries only when a concrete operation needs them.
- Keep metadata contracts application-owned. Advertise only supported capabilities;
  report existing claim/implementation discrepancies instead of silently hiding them.
  Check request/response semantics against the [OGC review guide](docs/validation.md#ogc-review-guide).
- Keep current guidance in `docs/` and the README. Do not maintain current status,
  copied instructions or future assignments in historical handover/milestone records.

## Checks

Preserve Ruff, Bandit, pytest/coverage, pre-commit and CI. Run applicable checks:

```bash
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts
uv run bandit -r src scripts -c pyproject.toml
uv run pytest --cov=geo_processes --cov-report=term-missing --cov-fail-under=70
```

For documentation-only work, check examples, links and `git diff --check`.
For behavior/deployment changes, also follow the configuration, OpenAPI and
container checks in the development guide. Report checks that could not run and
why. Never remove tests just to obtain a passing suite.
