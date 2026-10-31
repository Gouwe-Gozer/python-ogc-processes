# Development instructions

This repository implements Raster Processes API, a Rasterio/GDAL-backed OGC API –
Processes service built on pygeoapi. Code, configuration and tests define current
behavior. Use [development](docs/development.md), [architecture](docs/architecture.md)
and [validation](docs/validation.md) for maintained guidance.
Historical background is in [history](docs/history.md). `CODEX_HANDOVER.md`
is only a historical pointer, not an active task plan.
The Python package remains `geo_processes` (distribution `geo-processes`);
the public project/repository name is `raster-processes`.

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

`make test` runs these checks plus configuration/OpenAPI validation. `make validate`
adds the locked Geonovum comparison against an isolated API/PostgreSQL/worker
stack. `make validate-cite` runs the official executable suite against the same
combined deployment in a separate test project. Both workflows exercise async
execution; neither touches an existing deployment.
Keep reviewed baselines unchanged unless an explicit evidence-based update is
part of the task; documented CITE failures must remain failures. See the
[validation workflows](docs/validation.md#repeatable-commands).

## pygeoapi-first architecture
Prefer pygeoapi's existing APIs, managers, execution lifecycle and extension points.
Before changing shared infrastructure, inspect the relevant upstream interfaces
and justify why existing functionality is insufficient. Keep custom behavior
narrowly scoped and documented; avoid coupling processors to a particular manager.


## Rasterio/GDAL concurrency
Processing operations must not share open Rasterio/GDAL dataset handles across concurrent executions unless explicitly synchronized or supported by a documented thread-safe mechanism. Prefer opening datasets within each execution using context managers. Keep temporary files and output paths isolated per job. Preserve explicit concurrency and resource limits when introducing asynchronous execution.