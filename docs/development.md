# Development

Use user-installed `uv` and a project-local `.venv`. Python 3.12 remains the
tested interpreter: the official pygeoapi 0.24.0 image uses 3.12, and both pinned
packages work there. Changing Python is a separate compatibility decision.
No host system packages or global Python installs are needed.

```bash
uv sync --locked --all-groups
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts
uv run bandit -r src scripts -c pyproject.toml
uv run pytest --cov=terrio_processes --cov-report=term-missing --cov-fail-under=70
```

Tests include real loopback HTTP requests and need permission to bind a local
socket. They never download raster data. `uv run ruff format src tests scripts`
applies formatting. Dependency changes must include `pyproject.toml` and
`uv.lock` together. `.venv/`, project-local uv caches and generated API documents
are ignored. Pre-commit is configured to run the same Ruff and Bandit checks:
`uv run pre-commit install` enables the hooks for a checkout.

Validate the public configuration and generated definition:

```bash
uv run pygeoapi config validate --config config/pygeoapi.yml
uv run python -m terrio_processes.openapi --output pygeoapi-openapi.yml
uv run pygeoapi openapi validate pygeoapi-openapi.yml
```

Use the application generator above to match `/openapi`. The upstream
`pygeoapi openapi generate` command produces an uncorrected diagnostic document.
The compatibility tests explicitly compare that output with the runtime contract.

Start and test the self-contained release:

```bash
docker compose --file compose.release.yml config --quiet
docker compose --file compose.release.yml up --build --detach
uv run python scripts/smoke_discovery.py --base-url http://localhost:5001 --wait-seconds 60
uv run python scripts/check_release_container.py
docker compose --file compose.release.yml down --remove-orphans
```

The smoke test discovers the service and executes `terrio-info` through Terrio
in both raw and document modes. `compose.yml` additionally mounts source and
configuration read-only for development; restart after changing them.

The inherited CITE echo fixture remains separate from the public service:

```bash
PYTHONPATH=tests/fixtures uv run pygeoapi config validate --config config/pygeoapi.integration.yml
PYTHONPATH=tests/fixtures uv run pygeoapi openapi generate --format yaml --output-file /tmp/integration-openapi.yml config/pygeoapi.integration.yml
uv run pygeoapi openapi validate /tmp/integration-openapi.yml
docker compose -f compose.yml -f compose.integration.yml up --build --detach
```

That diagnostic configuration uses upstream TinyDB and `async-echo`; it is not
evidence that the public service implements asynchronous jobs. The public CI
retains quality checks, coverage, API validation, container execution/isolation
and pinned Geonovum diagnostics. Public process tests use the bundled raster
and do not depend on a live data service.
