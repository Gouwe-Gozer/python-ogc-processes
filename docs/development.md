# Development

Use user-installed `uv` and a project-local `.venv`. Python 3.12 remains the
tested interpreter: the official pygeoapi 0.24.0 image uses 3.12, and the pinned
application libraries work there. Changing Python is a separate compatibility decision.
No host system packages or global Python installs are needed.

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

## Extending the service

The [input flow](inputs.md) supports HTTPS references and inline base64 for
users' GeoTIFFs. Reusable uploads and new operations remain future work in the
[roadmap](roadmap.md). The completed [Rasterio pivot](rasterio-pivot.md) is the baseline.
Keep each operation's processor and contract separate, use small Python adapters,
and reuse the input/result lifecycle where appropriate.
Follow the [OGC review guide](validation.md#ogc-review-guide) for descriptions,
request validation, representations, OpenAPI and meaningful HTTP/raster tests.
Update README examples and the handover with the resulting public capabilities;
retain an explicit distinction between planned work and implemented behavior.

## Container and integration checks

Start and test the self-contained release:

```bash
docker compose --file compose.release.yml config --quiet
docker compose --file compose.release.yml up --build --detach
uv run python scripts/smoke_discovery.py --base-url http://localhost:5001 --wait-seconds 60
uv run python scripts/smoke_warp.py --base-url http://localhost:5001 --save-reference /tmp/warp-reference.txt
uv run python scripts/smoke_inputs.py --base-url http://localhost:5001
uv run python scripts/check_release_container.py
docker compose --file compose.release.yml restart api
uv run python scripts/smoke_discovery.py --base-url http://localhost:5001 --wait-seconds 60
uv run python scripts/smoke_warp.py --check-saved-reference /tmp/warp-reference.txt
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
the inline check from both the host and a separate client container. The pytest
suite exercises HTTPS through a local TLS origin and tests destination, redirect,
deadline, capacity and cleanup policies without contacting public services.

The local storage lock uses Linux `flock`; use Linux or Docker for this service.
See [result storage](results.md) for settings and maintenance commands.

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
and pinned Geonovum diagnostics. CI also downloads results from an independent
client container and verifies persistence across restart. Public process tests use
bundled or generated rasters and a local TLS fixture, without a live data dependency.

CI runs the Geonovum checker with Node.js 24 and npm 11.6.0. Its checkout,
Node setup and artifact-upload actions use releases with a native Node 24
runtime; `setup-uv@v7` also uses Node 24. Action runtimes and the checker runtime
are configured separately. Node/npm version output is retained in the job log.
The [checker baseline notes](../validation/geonovum/README.md) record the reproduced
Node 20/24 source-label difference. Diagnostic mismatch messages include their
source; inspect that field when findings appear as both added and removed.
