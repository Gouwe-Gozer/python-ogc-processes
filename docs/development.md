# Development

Normal Compose startup runs the API, PostgreSQL and a separate worker. See
[durable async execution](asynchronous-execution.md) for job handling, lifecycle
tests and the explicit database-free synchronous opt-out.

Run commands from the repository root with user-installed `uv` and a local
`.venv`. No host system packages or global Python installs are needed.

The project is **Python OGC Processes**, with repository name `python-ogc-processes`.
Its default deployed API title is **Python Processing Service**; [service metadata](release-image.md#service-identity)
can be customized independently of the project name.
Its existing Python package `geo_processes` and distribution `geo-processes`
remain unchanged.

| Component | Project constraint |
| --- | --- |
| Python | 3.12 (`>=3.12,<3.13` in `pyproject.toml`; `.python-version` selects 3.12) |
| pygeoapi | 0.24.0 |
| Rasterio | 1.4.3 |
| NumPy | 1.26.4 |

`pyproject.toml` declares dependencies; `uv.lock` fixes their resolved versions for
both local installation and Docker. The image temporarily mounts a digest-pinned
uv binary and runs `uv sync --locked --no-dev --no-install-project --inexact`
against its existing `/venv`. Stale locks fail the build; no manual Docker package
list or generated requirements file is maintained. The build accepts wheels only
and never downloads another Python interpreter.

`--inexact` preserves tools supplied by the digest-pinned pygeoapi base, including
Gunicorn, that are outside the application dependency graph. Those inherited
extras and OS/GDAL/PROJ components remain controlled by the base image/wheels.
The uv binary is not included in the final image. API and worker use the same image;
container tests compare every selected production requirement against the lock.
Update the manifest and lock together, then rebuild both services.

```bash
uv sync --locked --all-groups
make test
```

`make test` runs the existing Ruff/Bandit, configuration/OpenAPI and pytest/
coverage commands. GNU Make is needed; Python dependencies still come only from
uv. Reports are in `runtime-data/validation/`.

Tests include loopback HTTP and HTTPS servers and need permission to bind local
sockets. TLS uses public test-only fixtures, with no production bypass flag.
They never download public raster data. `uv run ruff format src tests scripts examples/custom-process`
applies formatting. Dependency changes must include `pyproject.toml` and
`uv.lock` together. `.venv/`, project-local uv caches and generated API documents
are ignored. Pre-commit is configured to run the same Ruff and Bandit checks:
`uv run pre-commit install` enables the hooks for a checkout.

Validate the public configuration and generated definition:

```bash
uv run pygeoapi config validate --config config/pygeoapi.yml
GEO_MANAGER_CLASS=geo_processes.manager.OgcSynchronousManager uv run python -m geo_processes.openapi --output pygeoapi-openapi.yml
uv run pygeoapi openapi validate pygeoapi-openapi.yml
```

The command above generates the explicit synchronous-only profile offline, as
used by fast unit tests and `make test`. To generate the combined definition
locally, set `GEO_JOB_DSN` to a reachable PostgreSQL database and omit that manager
override. Default runtime validation and CITE exercise the actual combined
configuration, including async OpenAPI/status/result responses. Use the
application generator to match `/openapi`. The upstream
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
environment settings by recreating the affected containers with `docker compose
up --detach` (include `--file compose.release.yml` for release). A plain restart
keeps the old container environment. The preflight is a configuration
check, rather than a storage capacity reservation or a memory/workload guarantee.

## Extending the service

Choose an [integration path](adding-a-process.md#choose-an-integration-path) and
check [deployment settings versus hard limits](release-image.md#resource-configuration).

Use the [Python process contribution recipe](adding-a-process.md) and its
[working independent example](../examples/custom-process/README.md) for registration,
shared API/worker installation and meaningful HTTP tests. Keep processors/contracts
independent and reuse the [input](inputs.md), [result](results.md) and
[exception](errors.md) lifecycles. Architectural boundaries are in
[architecture](architecture.md); proposed capabilities belong in the [roadmap](roadmap.md).
Update the relevant maintained guide when behavior changes.

## Container and integration checks

Compose derives its project name from the checkout directory; new checkouts named
`python-ogc-processes` use that project name. Keep an existing deployment's project
name explicit if renaming the directory; see [migration](release-image.md#repository-and-deployment-migration).
Both supplied API stacks use the same project and port 5001 by default; run one at
a time. Check `docker compose ls --all` when another container occupies the port.
An exported `COMPOSE_PROJECT_NAME`, `COMPOSE_FILE` or local `.env` setting can
override defaults; remove stale values rather than launching another copy.

For bind-mounted development, use `docker compose up --build --detach`.
Restart both services after processor source/configuration changes with
`docker compose restart api worker`; the worker also reads configuration at startup.
Use `docker compose --file compose.release.yml ...` consistently for release
commands. Switching files updates the same `api` service, rather than creating
independent development and release projects.

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
Both stacks retain named volumes for results and the PostgreSQL job database.
Normal `down` keeps both. For a deliberate reset of **all disposable local job
and result data** (never a database or results you need to keep):

```bash
docker compose --file compose.release.yml down --volumes --remove-orphans
docker compose --file compose.release.yml up --build --detach
```

Keep cleanup scoped to this Compose project; do not use global Docker prune.
`PYGEOAPI_TERMS_OF_SERVICE` is forwarded by both Compose configurations, like
the public URL and supported result/input settings. All existing `GEO_*`
defaults and limits remain unchanged.

The default manager uses `connection` (`GEO_JOB_DSN`) for durable PostgreSQL
jobs. Native `output_dir` remains in the pygeoapi configuration; application
file results use `GEO_OUTPUT_DIR`, while formatted async payloads live in the
database. Only the explicit synchronous manager ignores these native job-store
settings. See [job persistence](asynchronous-execution.md#persistence-and-interruption).

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

Keep reproducible raster tests independent of public Git branches. Current
Python tests use generated/packaged TIFFs and a local TLS origin; examples use
the packaged AHN4 sample or explicitly replaceable `data.example.org` placeholders.
The official schema snapshots are offline and checksummed. Optional live
`--source-href` checks should use a full upstream commit SHA and record the
raster checksum, comparing with the same local `--input-raster`. The project's
`blob/main/docs/errors.md` URLs identify maintained exception documentation;
they are not raster fixtures.

The local storage lock uses Linux `flock`; use Linux or Docker for this service.
See [result storage](results.md) for settings and maintenance commands.

## Runtime logging

The service retains the configured `logging.level` (INFO by default). A narrow
filter removes pygeoapi 0.24.0's false unknown-locale warnings for registered
schema/example/link and literal processor configuration keys, such as `type`,
`coordinates` and `name`. It leaves upstream
translation and metadata unchanged; nonmatching locale diagnostics and all other
warnings/errors remain visible. See [the compatibility boundary](architecture.md#compatibility-corrections).

The pinned release's Rasterio polygonization can emit a GDAL warning that its
internal `Memory` driver is deprecated in favor of `MEM`. Processing and GeoJSON
delivery still succeed. This upstream warning is retained; resolving it requires
reviewing the Rasterio/GDAL dependency pair, rather than filtering diagnostics.

The image does not set `PYGEOAPI_ASYNCAPI`: no AsyncAPI document or pub/sub
interface is configured. This avoids requesting a nonexistent optional file
at each worker startup. Explicitly supplied AsyncAPI paths still use upstream
loading and diagnostics. AsyncAPI describes event interfaces; it is separate
from asynchronous OGC process jobs.

## API documentation UI

`/openapi?f=html` uses upstream Swagger UI. `/openapi?f=html&ui=redoc` uses a
small packaged template override with ReDoc **2.5.3** pinned on jsDelivr. The
stock pygeoapi template uses an unversioned classic script; ReDoc 3 changed that
bundle to an ES module, causing a blank page. See
[Redocly's migration notice](https://redocly.com/blog/redoc-3-release).

The override uses pygeoapi's supported template path and the configured API URL,
including path prefixes. Other templates fall back to upstream defaults; an
explicit operator template path takes precedence over this default. ReDoc
requires browser access to the external CDN. The page also links directly to
the OpenAPI JSON, which remains usable without the renderer.

The application OpenAPI generator removes only top-level tag declarations
unused by any HTTP operation, avoiding empty UI sections inherited from
pygeoapi's other API modules. Paths, operation tags, retained tag metadata and
their order are preserved. The shared service description comes from
`metadata.identification.description` in `config/pygeoapi.yml`; it describes
intended OGC alignment without claiming certification.

The separate upstream-manager diagnostic is checked by `make test`:

```bash
mkdir -p runtime-data
PYTHONPATH=tests/fixtures uv run pygeoapi config validate --config config/pygeoapi.integration.yml
PYTHONPATH=tests/fixtures uv run pygeoapi openapi generate --format yaml --output-file runtime-data/integration-openapi.yml config/pygeoapi.integration.yml
uv run pygeoapi openapi validate runtime-data/integration-openapi.yml
```

This TinyDB/`async-echo` configuration tests compatibility with upstream manager
behavior and native OpenAPI generation. It does not represent the default
deployment and is not the current CITE runner's configuration. Do not substitute
it for the combined stack when assessing this service.

## External validation and CI

Use [validation](validation.md#repeatable-commands) for `make validate-geonovum`,
`make validate` and `make validate-cite`, CI scope and report interpretation.
Both external workflows normally start isolated API/PostgreSQL/worker stacks;
neither needs or changes the ordinary deployment. An explicit `GEONOVUM_INPUT`
override targets an existing API. Docker supplies Node/Java/TEAM Engine.

Tool-specific instructions live with [Geonovum](../validation/geonovum/README.md)
and [CITE](../validation/cite-teamengine/README.md). Keep exact reviewed baselines
and raw failures intact; investigate changed diagnostics before proposing updates.
