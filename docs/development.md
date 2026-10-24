# Development

Run commands from the repository root with user-installed `uv` and a local
`.venv`. No host system packages or global Python installs are needed.

| Component | Project constraint |
| --- | --- |
| Python | 3.12 (`>=3.12,<3.13` in `pyproject.toml`; `.python-version` selects 3.12) |
| pygeoapi | 0.24.0 |
| Rasterio | 1.4.3 |
| NumPy | 1.26.4 |

`pyproject.toml` and `uv.lock` define local dependencies. The Dockerfile pins the
official pygeoapi base by digest and uses its `/venv` interpreter. These three
application library versions match; transitive packages and bundled GDAL/PROJ
versions may differ. Check both environments when changing processing behavior.

```bash
uv sync --locked --all-groups
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts
uv run bandit -r src scripts -c pyproject.toml
uv run pytest --cov=geo_processes --cov-report=term-missing --cov-fail-under=70
```

Tests include loopback HTTP and HTTPS servers and need permission to bind local
sockets. TLS uses public test-only fixtures, with no production bypass flag.
They never download public raster data. `uv run ruff format src tests scripts`
applies formatting. Dependency changes must include `pyproject.toml` and
`uv.lock` together. `.venv/`, project-local uv caches and generated API documents
are ignored. Pre-commit is configured to run the same Ruff and Bandit checks:
`uv run pre-commit install` enables the hooks for a checkout.

Validate the public configuration and generated definition:

```bash
uv run pygeoapi config validate --config config/pygeoapi.yml
uv run python -m geo_processes.openapi --output pygeoapi-openapi.yml
uv run pygeoapi openapi validate pygeoapi-openapi.yml
```

Use the application generator above to match `/openapi`. The upstream
`pygeoapi openapi generate` command produces an uncorrected diagnostic document.
The compatibility tests explicitly compare that output with the runtime contract.

## Startup validation

Inspect and validate the effective configuration before starting a service:

```bash
uv run python -m geo_processes.startup --config config/pygeoapi.yml
```

The owned container entrypoint runs this preflight before generating OpenAPI and
launching Gunicorn. Direct imports of `geo_processes.app:APP` validate the same
settings. The command prints the canonical public URL, registered process IDs,
worker settings, input bounds/host policy and result location/retention/quotas.
It creates missing input/result directories and briefly probes write access;
it does not execute a process, delete results or run storage cleanup.

Invalid settings stop startup with a named configuration error. Checks cover:

- `server.url` (normally `PYGEOAPI_SERVER_URL`): absolute ASCII HTTP(S), optional
  proxy prefix and valid port; no credentials, query, fragment or whitespace.
  Reachability from a real client still needs an HTTP check.
- `GEO_INPUT_TMPDIR` and `GEO_OUTPUT_DIR`: writable, separate directories with
  neither inside the other. Defaults are `runtime-data/inputs` and
  `runtime-data/results`; Compose uses `/tmp/geo-inputs` and `/var/lib/geo/results`.
- `GEO_INPUT_ALLOWED_HOSTS`: empty or comma-separated exact ASCII hostnames/IPs;
  no URLs, wildcards or empty entries. Public-address/TLS checks still apply.
- Result retention/capacity/count settings: see the authoritative
  [bounds and defaults](results.md#bounds-and-configuration).
- `CONTAINER_PORT`: 1–65535 (default 8080); `WSGI_WORKERS` and
  `WSGI_WORKER_TIMEOUT`: positive integers (defaults 2 and 30 seconds).

Worker/bind overrides apply when supplied to the container environment; Compose's
external `API_PORT` and `PYGEOAPI_SERVER_URL` remain separate settings. Change
operational settings by restarting the service. The preflight is a configuration
check, rather than a storage capacity reservation or a memory/workload guarantee.

## Extending the service

Use the [operation contribution recipe](adding-a-process.md) for the file map,
contract checklist and meaningful raster/HTTP tests. Keep processors/contracts
independent and reuse the [input](inputs.md), [result](results.md) and
[exception](errors.md) lifecycles. Architectural boundaries are in
[architecture](architecture.md); proposed capabilities belong in the [roadmap](roadmap.md).
Current implementation changes should update maintained documentation, not the
historical handover.

## Container and integration checks

For bind-mounted development, use `docker compose up --build --detach`.
Restart the API after source/configuration changes with `docker compose restart api`.

Start and test the self-contained release:

```bash
mkdir -p runtime-data
docker compose --file compose.release.yml config --quiet
docker compose --file compose.release.yml up --build --detach
uv run python scripts/smoke_discovery.py --base-url http://localhost:5001 --wait-seconds 60
uv run python scripts/smoke_warp.py --base-url http://localhost:5001 --save-reference runtime-data/warp-reference.txt
uv run python scripts/smoke_inputs.py --base-url http://localhost:5001
uv run python scripts/check_release_container.py
docker compose --file compose.release.yml restart api
uv run python scripts/smoke_discovery.py --base-url http://localhost:5001 --wait-seconds 60
uv run python scripts/smoke_warp.py --check-saved-reference runtime-data/warp-reference.txt
docker compose --file compose.release.yml down --remove-orphans
```

The discovery test executes `raster-info`; the warp test exercises all four
response/transmission combinations and opens the resulting GeoTIFFs. The saved
reference verifies persistence across a service restart. `compose.yml` mounts
source and configuration read-only for development; restart after changing them.
Both stacks use a named result volume. Normal `down` retains it; adding
`--volumes` deletes it and all stored results.

The input smoke check creates a two-band raster independently of the bundled
demo, submits it inline, checks info and all four warp modes, then downloads
results. `--input-raster my-dem.tif` uses your file; `--source-href https://...`
instead submits a hosted copy of that file for independent comparison. CI runs
the inline check from both the host and a separate client container. It also
samples Point, MultiPoint and Point FeatureCollection inputs, reclassifies a band
and downloads polygonized GeoJSON from the classified result. Polygonization is
skipped for custom rasters above its pixel limit. The pytest suite exercises
HTTPS through a local TLS origin and tests destination, redirect,
deadline, capacity and cleanup policies without contacting public services.

The local storage lock uses Linux `flock`; use Linux or Docker for this service.
See [result storage](results.md) for settings and maintenance commands.

The inherited CITE echo fixture remains separate from the public service:

```bash
mkdir -p runtime-data
PYTHONPATH=tests/fixtures uv run pygeoapi config validate --config config/pygeoapi.integration.yml
PYTHONPATH=tests/fixtures uv run pygeoapi openapi generate --format yaml --output-file runtime-data/integration-openapi.yml config/pygeoapi.integration.yml
uv run pygeoapi openapi validate runtime-data/integration-openapi.yml
docker compose -f compose.yml -f compose.integration.yml up --build --detach
```

That diagnostic configuration uses upstream TinyDB and `async-echo`; it is not
evidence that the public service implements asynchronous jobs. It replaces the
public configuration when using the Compose override, so run the stacks separately.

CI runs quality, configuration/OpenAPI and release-container checks on `main`
pushes, pull requests and manual dispatches. The Geonovum comparison runs only
on pull requests and manual dispatches, using Node 24 and npm 11.6.0. Diagnostic
source handling and the reviewed findings are documented in the
[checker notes](../validation/geonovum/README.md). Runtime checks include independent
client containers, result downloads and persistence across restart.
