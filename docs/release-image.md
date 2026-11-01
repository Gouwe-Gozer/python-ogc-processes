# Release deployment

`compose.release.yml` builds a self-contained image with application source,
canonical configuration and licence notices. Its official pygeoapi 0.24.0 base
is pinned by manifest digest in `docker/Dockerfile`. The build installs production
Python dependencies directly from `pyproject.toml` / `uv.lock` into the same `/venv`
used by Gunicorn. A temporary, digest-pinned uv tool validates the lock and installs
wheels without development groups or the project package; source/configuration
packaging remains unchanged. API and worker use this same image.

Docker BuildKit is required for the temporary build mounts (the default with
modern Docker). Registry/Python package downloads are needed during uncached builds.
The final image contains no uv binary or separately maintained dependency list.
Inherited base-image tools such as Gunicorn are retained; their versions and OS
components remain pinned by the base-image digest. Platform-specific GDAL/PROJ
resources may differ from local development. See [dependency workflow](development.md).

## Run and inspect

```bash
docker compose --file compose.release.yml up --build --detach
uv run python scripts/check_release_container.py
docker compose --file compose.release.yml exec -T api /venv/bin/python3 -c 'import rasterio, numpy, pygeoapi; print(rasterio.__version__, rasterio.__gdal_version__, numpy.__version__, pygeoapi.__version__)'
```

The isolation checker needs the local [development environment](development.md).
Run the [container smoke checks](development.md#container-and-integration-checks)
to verify discovery, actual processing, all result modes and restart persistence.
A health check alone only fetches `/conformance`.

## Resource configuration

Settings are shared by the deployment, not selected by each process request.
Use the existing Compose files plus an explicit override; no new configuration
layer is required. This map separates deployment settings from application limits.

| Setting | Current default and scope | Where to change it |
| --- | --- | --- |
| CPU/RAM/processes | API and worker each: 1 CPU, 512 MiB RAM, 128 processes; PostgreSQL: 256 MiB RAM | Override `cpus`, `mem_limit`, `pids_limit` on the relevant services; defaults are in `compose.base.yml`. |
| Sync concurrency/timeout | API: two Gunicorn workers, 30 seconds per worker | Container environment `WSGI_WORKERS` / `WSGI_WORKER_TIMEOUT`; see [startup settings](#startup-and-public-url). These do not increase async concurrency. |
| Async concurrency/timeout | One executing job per dedicated database; 30-second child deadline | `GEO_JOB_TIMEOUT` accepts **1–300 seconds**. The single-worker policy is coded; adding worker replicas is rejected. See [job bounds](asynchronous-execution.md#bounds-and-lifetime). |
| Request body | 24 MiB for the application | Hardcoded `inputs.MAX_EXECUTION_BYTES`, applied by Flask; not a Compose setting. |
| Raster helper inputs | 16 MiB, 1,048,576 samples including bands; 16 MiB decoded blocks/cache | Hardcoded in `engine.py`; applies to the bundled raster resolver/operations, not every Python function. |
| JSON/scalar helper inputs | JSON parameters: 256 KiB; scalar references: 4 KiB | Hardcoded in `inputs.py`; changing metadata alone does not change validation. |
| HTTPS acquisition | Public HTTPS/443, ten-second fetch deadline, three-second socket operations, three redirects, two input slots per directory | Security/transport limits are coded in `inputs.py`; `GEO_INPUT_ALLOWED_HOSTS` can narrow destinations. See [input policy](inputs.md). |
| Temporary storage | Separate 64 MiB `/tmp` tmpfs for API and worker; staging `/tmp/geo-inputs` | Override each service's `tmpfs` or add deliberate data/cache mounts. `GEO_INPUT_TMPDIR` changes the staging path; mounts must agree. |
| Persistent file results | Shared `results` volume at `/var/lib/geo/results`; locally `runtime-data/results` | `GEO_OUTPUT_DIR` and matching API/worker mounts. Capacity/expiry use `GEO_RESULT_*`; [result settings](results.md#bounds-and-configuration) own defaults and ranges. |
| Individual file delivery | Existing store: TIFF/GeoJSON, at most **16 MiB per file** | Hardcoded `storage.MAX_RESULT_BYTES` / `RESULT_TYPES`. Raising total store capacity does not raise this limit. |
| Retained async payloads | Requests/results in PostgreSQL's `jobs-db` volume, with a shared admission budget | `GEO_JOB_MAX_COUNT` / `GEO_JOB_MAX_BYTES`; see [job bounds](asynchronous-execution.md#bounds-and-lifetime). Binary results are base64 in stored responses, not streamed from the worker. |
| Dependencies | One locked Python environment and shared image for API/worker | `pyproject.toml` / `uv.lock`; [installation paths](adding-a-process.md#3-install-and-register-explicitly). Registry wheels are supported; local/source builds need deliberate build inputs. |
| Process formats/options | Declared and validated by each processor | Metadata, wrapper validation and explicit `processor` configuration fields; no automatic per-process resource policy. Native by-value output can use other media types; the file-store allowlist is separate. |

Compose forwards `GEO_JOB_TIMEOUT`, `GEO_JOB_MAX_COUNT`, `GEO_JOB_MAX_BYTES`,
`GEO_JOB_PASSWORD`, `GEO_RESULT_*` and `GEO_INPUT_ALLOWED_HOSTS` from the environment
or `.env`. It constructs `GEO_JOB_DSN` from the database credentials; changing that
connection string needs an explicit override.

CPU/RAM, Gunicorn settings, directory mounts and tmpfs changes need an explicit
Compose override. For example, save this as your own `compose.workload.yml`:

```yaml
services:
  api:
    environment:
      WSGI_WORKER_TIMEOUT: "60"
  worker:
    mem_limit: 2g
    cpus: 2.0
```

```bash
GEO_JOB_TIMEOUT=120 docker compose -f compose.release.yml -f compose.workload.yml up --build --detach
```

Keep the same project name and override arguments for subsequent commands.
Recreate containers after environment/deployment changes; plain `restart` does
not apply a changed environment. File/job quotas are application publication
budgets, not filesystem/database-size quotas. Process models and caches need
explicit paths/mounts because the root filesystem is read-only.

For workloads that fit the existing input/output interfaces, more CPU/RAM and
an async timeout up to five minutes need deployment changes only. Longer jobs,
additional downloadable file types, larger files through the existing raster
resolver/store, per-process dependency isolation or parallel
async workers need application work. Each async job gets a fresh child, including
initialization overhead; persistent model reuse and GPU execution are not
demonstrated. Keep the existing security controls when assessing a new workload.

## Service identity

Python OGC Processes is the application/repository name. The default deployed API
title is **Python Processing Service**. `metadata.identification.title` and
`description` in `config/pygeoapi.yml` use pygeoapi's native YAML environment
substitution with optional `PYGEOAPI_TITLE` / `PYGEOAPI_DESCRIPTION` overrides.
When unset, the description is:

> An extensible, standards-oriented OGC API – Processes application for integrating and executing custom Python workflows, built on pygeoapi.

Compose forwards these optional variables to API and worker without duplicating
defaults. Keep these placeholders as plain YAML scalars: pygeoapi does not expand
quoted or block-string placeholders. When copying a config with Python, use
`yaml.safe_dump(config, allow_unicode=True)` to preserve this form for the Unicode
description. Set overrides in the host environment or `.env`, then recreate containers:

```bash
PYGEOAPI_TITLE='Municipal Processing Service' \
PYGEOAPI_DESCRIPTION='Python workflows for municipal data.' \
  docker compose --file compose.release.yml up --build --detach
```

The title/description appear in landing responses and generated OpenAPI. HTML
templates retain their existing rendering/escaping behavior. Configuring metadata
does not rename process IDs, change execution capabilities or establish OGC
certification. As with other environment changes, plain `restart` keeps old values.

## Startup and public URL

The owned entrypoint validates runtime settings and prints the effective public
URL, process IDs, input policy and result limits. It then generates OpenAPI in
`/tmp` and starts two synchronous Gunicorn workers, with a 30-second timeout,
on internal port 8080. Directory probes do not delete stored results.
See [startup validation](development.md#startup-validation) for exact checks.

Compose publishes port 5001 by default. Set `API_PORT` and `PYGEOAPI_SERVER_URL`
together when changing the external address:

```bash
API_PORT=5002 PYGEOAPI_SERVER_URL=http://localhost:5002 docker compose --file compose.release.yml up --build --detach
```

Generated links use that canonical URL, including any proxy prefix, rather than
the requesting Host header. URL validation does not test client reachability.

`WSGI_WORKERS`, `WSGI_WORKER_TIMEOUT` and `CONTAINER_PORT` are container environment
settings. Supply overrides through an explicit Compose override or another
container launcher; these variables are not forwarded from the host by the
supplied Compose files. A bind-port override also needs matching port mapping
and health-check configuration.

## Reverse proxy and TLS termination

Set `PYGEOAPI_SERVER_URL=https://raster.example.org/geo` before starting the API
when that is the client-facing base. This explicit configuration controls
discovery and result links; incoming `Host` and `X-Forwarded-*` headers do not
replace it. Recreate both API and worker after environment changes:
`docker compose --file compose.release.yml up --detach`. Plain `restart` retains
the existing environment; the API entrypoint regenerates OpenAPI on startup.

The proxy can terminate trusted public TLS on port 443 and forward to internal
HTTP port 8080 (or the host's published port). With `/geo` only in `server.url`,
strip that external prefix before forwarding: the native routes are still at
`/processes`, `/results`, etc. If using pygeoapi's additional
`server.api_rules.url_prefix`, retain that native prefix upstream and update any
explicit resource links accordingly. Result links reuse pygeoapi's computed base
URL, including that prefix. URL-prefix tests cover both deployment shapes.

Preserve response statuses, `Link` headers, media types and attachment headers;
a raw/reference result is intentionally an empty HTTP 204. For reference inputs,
the API container needs outbound access to the public origin. See
[chaining requirements](inputs.md#chain-raster-operations), including public DNS,
identity content encoding and available worker capacity. No TLS-termination,
trusted-proxy middleware or production hostname is provisioned by this image.

## Isolation and storage

Both development and release Compose give each API/worker container:

- UID/GID `10001:10001`, read-only root, dropped capabilities and `no-new-privileges`;
- a 64 MiB `/tmp` tmpfs with `noexec,nosuid`, including private input workspaces;
- one writable named volume, `results`, mounted at `/var/lib/geo/results`;
- resource budgets from the [configuration map](#resource-configuration).

The image initializes result-directory ownership before dropping privileges.
No source/configuration bind mounts or runtime root initialization are required.
Development inherits the same restrictions from `compose.base.yml` and adds
read-only source/configuration mounts. A bare `docker run` needs equivalent
explicit settings. PostgreSQL has its own `jobs-db` volume and memory limit.

The [input policy](inputs.md) covers HTTPS restrictions, decoding and cleanup.
The [result guide](results.md) owns retention, capacity, locking and maintenance
settings. There is no built-in authorization: job metadata is discoverable
through `/jobs`, and job/file results are accessible until expiry. See the
[security boundary](../SECURITY.md#jobs-and-deployment).

A normal `docker compose --file compose.release.yml down` retains **both result
and job-database volumes**. Adding `--volumes` deletes both; reserve it for an
intentional reset of disposable data. Keep the same Compose project name when
renaming a checkout or upgrading an existing installation, so Docker reuses the
same volumes. A new checkout named `python-ogc-processes` uses result volume
`python-ogc-processes_results` and database volume `python-ogc-processes_jobs-db`.
Older installations keep their existing names; see [migration](#repository-and-deployment-migration). See [local reset instructions](development.md#container-and-integration-checks)
when disposable job and result data should be discarded deliberately.

Authentication, TLS termination, hosting, monitoring and access/egress policy
remain deployment responsibilities; this repository supplies a bounded service
and release artifact rather than managed production operations.

## Deployment services

`compose.release.yml` uses the shared `compose.base.yml` definition: one API,
PostgreSQL and one independent worker using the same release image. Job requests,
state and formatted results persist in the database volume; file downloads use
the shared result volume. Ordinary requests are synchronous; `respond-async`
uses the worker. Set `GEO_JOB_PASSWORD` for hosted use and retain it across
restarts; the default password is for local development only. The database is
not exposed on a host port.

Apply `-f compose.sync.yml` after the release file to start the database-free,
synchronous-only API. See [execution and deployment details](asynchronous-execution.md).

## Repository and deployment migration

The project/repository is now **Python OGC Processes** / `python-ogc-processes`,
formerly Raster Processes API / `raster-processes`. The repository owner renames
it on GitHub. After that change, update a local clone yourself:

```bash
git remote set-url origin https://github.com/Gouwe-Gozer/python-ogc-processes.git
```

This change does not update remotes or rename local directories automatically.
GitHub redirects ordinary repository/Git URLs after a rename; do not reuse the
old repository name while depending on those redirects. See [GitHub's migration guidance](https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository).

| Identifier | Migration |
| --- | --- |
| Python distribution/imports | Keep `geo-processes` / `geo_processes`; no dependency/import migration. |
| Release/development images | Rebuild as `python-ogc-processes:0.1.0` / `python-ogc-processes-dev:0.1.0`. Update external launchers or derived Dockerfiles using old tags. CI and the custom example use the new tags. |
| Image licence notices | Stored at `/licenses/python-ogc-processes/`; update external tooling that reads the former image-internal directory. |
| Compose project/volumes | Names still derive from the checkout directory. Renaming it changes the default project and therefore selects different volumes. Retain the old project explicitly to reuse existing data. |
| Environment/configuration | Existing `GEO_*`, `PYGEOAPI_SERVER_URL`, storage paths, database/role and local-only password defaults remain unchanged. Title/description overrides are optional additions. |
| HTTP contracts | Process IDs, routes and execution modes remain unchanged. Service-defined exception `type` URIs keep their legacy namespace; see [exceptions](errors.md). |
| Reports and validation IDs | Dated native reports and existing `raster-cite-*`, `raster-geonovum-*`, `raster-async-test-*` namespaces are retained for traceability and operational continuity. |

For an existing project actually named `raster-processes`, use the same explicit
project argument for **all** deployment/inspection/stop commands after moving the
checkout, for example:

```bash
docker compose --project-name raster-processes --file compose.release.yml up --build --detach
```

This reuses its job/result volumes. Stop the previous development/release services
deliberately before switching deployment mode or project name; do not use
`down --volumes` to migrate persistent data. Choosing a new project name while
retaining data needs a deliberate backup/volume migration, not a naming-only edit.
The custom example projects are now `python-ogc-custom-example` and
`python-ogc-custom-release`, formerly `raster-custom-example` and
`raster-custom-release`. These names select separate disposable volumes; retain
the previous `-p` name if you need those results/jobs.

Renaming the local checkout is optional. If you do, recreate its path-dependent
virtual environment (`uv venv --clear`, then `uv sync --locked --all-groups`).
Update personal scripts, bookmarks and deployment references. These workflows
do not publish a reusable GitHub Action, a Pages site or registry images; external
deployments/publications must update their own names separately. Python package
metadata uses the new description/repository URL while retaining its distribution
name; any published update follows the normal package release/versioning process.
