# Codex instructions

This repository is pivoting from `terrio-processes` to `geo-processes`, a Rasterio-backed OGC API – Processes service built on pygeoapi. The user approved the pivot and library-neutral name. Follow `CODEX_HANDOVER.md` and `docs/rasterio-pivot.md` for current status; keep additions small and operation-specific.

## Environment

- Use the user-installed `uv` and a project-local `.venv` (`uv sync --locked --all-groups`, then `uv run ...`). Do not install project packages into system Python.
- Inspect `pyproject.toml`, `uv.lock`, and any `.python-version` before choosing or changing a Python version. Don't assume the previous Python 3.12 pin is necessary; verify compatibility before changing it.
- Never use `sudo`, `apt`, global `pip`, or `--break-system-packages`, and don't modify files outside this repository without asking first.
- Keep `.venv/` out of version control. Commit intentional dependency and lockfile updates together.

## Implementation

- Reuse the existing pygeoapi configuration, synchronous execution contract, tests, and CI where possible. Preserve the MIT licence and copyright notices for reused infrastructure.
- Keep OGC processors separate from small Python adapters. Use Rasterio/GDAL for the approved raster pivot and remove the Terrio runtime dependency. Do **not** add a generalized engine plugin system or asynchronous job infrastructure for this prototype.
- Add Shapely, Pyogrio or GeoPandas usage only when a concrete operation needs it. Keep metadata contracts application-owned rather than tied to a library's native dictionary.
- Give each new operation its own process implementation and description. Don't hardcode JSON-only, single-output, or value-only assumptions into shared infrastructure.
- Advertise only supported OGC API – Processes capabilities. Use the standard and official examples linked in `CODEX_HANDOVER.md` to check request and response semantics.

## Checks

Preserve the existing Ruff, Bandit, pytest/coverage, pre-commit, and CI configuration; adapt paths and package names rather than replacing the tooling. Run applicable checks before finishing, including:

```bash
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts
uv run bandit -r src scripts -c pyproject.toml
uv run pytest --cov=terrio_processes --cov-report=term-missing --cov-fail-under=70
```

Adjust paths if the new repository does not contain `scripts/` or has a different package name. Report checks you couldn't run and why. Never delete tests just to make the suite pass.
