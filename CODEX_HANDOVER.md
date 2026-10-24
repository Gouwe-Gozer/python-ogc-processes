# geo-processes — current handover

The approved [Rasterio pivot](docs/rasterio-pivot.md) replaces the previous Terrio
runtime and names with **geo-processes** (`geo_processes`). GDAL-free deployment
is no longer a goal. The pivot was merged into `main` at `88a83a2`; its obsolete
branches were removed after verifying equivalent changes. The user-raster
milestone was merged into `main` at `244667a`. Service usability work is on
`feat/service-usability`, based on that merged `main`; external client changes
remain a separate follow-up after this service branch is reviewed/merged.
The remote GitHub repository retains its existing name.

`geo-processes` exposes bounded Rasterio operations through OGC API – Processes
using the official pygeoapi package. Maintainer: Minnert Wijnands (Gouwe-Gozer).
`raster-info` and the first file-producing operation, `raster-warp`, are
implemented. See [README](README.md) for usage and
[development](docs/development.md) for setup and checks.

The end goal is processing **users' own rasters**, not only an operator-hosted
catalogue. Follow the [roadmap](docs/roadmap.md) for the proposed next milestones
and the [OGC review guide](docs/validation.md#ogc-review-guide) for contract work.

## Current implementation

- Python 3.12, pygeoapi **0.24.0**, Rasterio **1.4.3** and NumPy **1.26.4**, with project-local
  dependencies managed by `uv` and pinned in `uv.lock`.
- Two public processes: **`raster-info`** and **`raster-warp`**. Their required
  `source` accepts a controlled HTTPS reference, direct base64 string or qualified
  inline base64 GeoTIFF. The bundled 4 by 3 fixture is submitted as ordinary input
  by tests and smoke clients; `demo-dem` is not a public input. Clients cannot choose
  filesystem paths, raw URL strings or arbitrary Rasterio options.
- The shared [input resolver](src/geo_processes/inputs.py) stages at most two
  private inputs, checks public destinations/redirects, pins TLS connections and
  enforces limits. Files are removed after execution or cleaned on slot reuse
  after a worker crash. See [input policy and examples](docs/inputs.md).
- The plain Python adapter reads metadata with Rasterio, computes exact finite
  masked statistics with NumPy and calls `rasterio.warp.reproject` for each band.
  Metadata uses an [application-owned contract](docs/raster-info.md).
  Only GTiff reads staged files; PAM/sidecars and PROJ networking are disabled.
  User rasters are fully validated before processing. JSON requests are capped
  at 24 MiB; raster bytes at 16 MiB, samples at 1,048,576 including bands, and
  decoded blocks at 16 MiB. Invalid inputs return 400, oversized bytes/bodies
  413, and busy temporary input slots 503.
  Each processor owns its input validation, description and result formatting.
- Synchronous execution only: `jobControlOptions: ["sync-execute"]`.
  Info offers value transmission; warp offers value and reference. Omitted
  `response` means `raw`; omitted `outputs` selects the defined output; omitted
  transmission means `value`.
- Info raw execution returns application-defined raster information with HTTP 200 and
  `application/json`. Document execution returns HTTP 200 and
  `{"info":{"value":{...raster information...}}}`. `Prefer: respond-async`
  remains synchronous and does not advertise a job URL.
- Warp accepts EPSG:28992/4326/3857 and nearest/bilinear resampling (default
  bilinear), retaining source grid dimensions. Raw/value returns TIFF bytes;
  document/value returns base64 with media type/encoding; document/reference
  returns a download URL; raw/reference returns empty HTTP 204 plus a Link header.
- Outputs live in a bounded named Docker volume, with 24-hour expiry by
  default. Quotas and a cross-worker file lock return 503 when full or busy.
  Expiry is enforced on reads; cleanup happens before new warps or through the
  cleanup command. See [result lifecycle](docs/results.md).
- Unknown inputs/outputs, unsupported formats/transmission, callbacks and
  malformed requests are rejected with JSON client errors. Engine failures
  return sanitized server errors. The [JSON exception catalogue](docs/errors.md)
  supplies stable `type` URIs and problem details while retaining legacy
  `code`/`description` fields; unknown processes use the URI from Requirement 15.
- `scripts/process_raster.py` provides a user-facing local-file flow: inspect,
  reproject, request a reference and save the download without overwriting an
  existing file. Exhaustive smoke scripts remain separate developer checks.
- Startup validates the canonical URL, numeric limits, host allowlist and
  separate writable input/result directories before accepting requests. The
  entrypoint prints effective configuration before launching Gunicorn. See
  [startup validation](docs/development.md#startup-validation).
- Docker uses the pinned official pygeoapi image and installs Rasterio in the
  same `/venv` used by Gunicorn. Release Compose retains non-root execution,
  a read-only root, bounded `/tmp`, dropped capabilities and no-new-privileges.

## Code and validation map

| Location | Responsibility |
| --- | --- |
| `src/geo_processes/engine.py` | Rasterio adapter without pygeoapi imports |
| `src/geo_processes/processes/` | Independent info and warp validation/representations |
| `src/geo_processes/contracts/` | Per-operation metadata and schemas |
| `src/geo_processes/datasets.py` | Demo file and ordinary inline requests for tests/smoke clients |
| `src/geo_processes/inputs.py` | Bounded HTTPS/base64 resolution and private input lifecycle |
| `src/geo_processes/contracts/sources.py` | Raster value schemas and supported OGC wire forms |
| `src/geo_processes/storage.py` | Bounded local output publication, expiry and cleanup |
| `src/geo_processes/responses.py` | Explicit process HTTP representation |
| `src/geo_processes/app.py` | Boundary validation for registered execution routes |
| `src/geo_processes/errors.py` | JSON exception URI catalogue and compatible legacy fields |
| `src/geo_processes/startup.py` | Effective settings, directory preflight and startup summary |
| `src/geo_processes/manager.py` | Synchronous execution and typed/sanitized errors |
| `src/geo_processes/openapi.py` | Version-checked corrections to upstream OpenAPI |
| `config/pygeoapi.yml` | Public resource and manager registration |
| `docker/`, `compose*.yml` | Application startup and deployment configurations |
| `tests/`, `scripts/`, `.github/workflows/ci.yml` | Unit, official-schema, HTTP, quality and container checks |

Follow [adding a process](docs/adding-a-process.md) for the operation file map,
OGC review points and contribution checklist. No automatic engine registration
or new dependencies were introduced for the usability work.

Keep the tested compatibility corrections until equivalent HTTP tests establish
that upstream handles them. The pinned DummyManager's document wrapper and
exception handling, malformed execute shapes, unconditional Callback claim,
generated discovery/execution schemas and metadata mutation still need the
current corrections. No upstream Python source or entrypoint is patched.

The integration-only `async-echo`/TinyDB configuration is a diagnostic fixture,
not a public capability. The pinned Geonovum checker has five recorded job/async
diagnostics. Historical CITE results describe the predecessor service, not this
implementation. See [validation](docs/validation.md) for the evidence boundary
and [migration report](docs/migration.md) for the initial compatibility inventory.

The current suite has 360 passing tests and 95.33% coverage, including checker
source comparisons, JSON exception semantics, startup settings and the local-file
client against real HTTP. CI uses Node 24 and native Node 24 actions.
It uses the OGC binary value convention without a demo/transport union. Earlier
milestone evidence includes checked host/container flows and a Float32 workload. See
[milestone evidence](docs/inputs.md#milestone-validation); retain the limits until
broader workloads justify increasing them.

## Working rules

Follow [AGENTS.md](AGENTS.md). Use user-installed `uv`, a local `.venv` and
`uv run` for Python commands. Preserve Ruff, Bandit, pytest/coverage,
pre-commit and CI; keep dependency and lockfile changes together. Inspect the
Python constraints and compatibility before changing the interpreter.

Keep operations independent and narrowly defined. Shared infrastructure must
not assume that every future process has one JSON output or value transmission.
Do not add a generic engine plugin system, asynchronous jobs or
arbitrary remote data access as incidental work on the current milestone.
Do not commit, push or publish unless the user requests it.

## Further milestones

The first own-raster flow supports HTTPS references and inline base64, as chosen
by the user. Preserve this pilot while expanding representative real-data tests,
useful warp grid controls and deployment policies. Reusable upload storage is a
separate future decision; an operator catalogue is optional. See the
[roadmap](docs/roadmap.md). Do not add arbitrary driver strings, private URL
destinations or asynchronous infrastructure incidentally.

Useful warp resolution/extent controls and subsequent raster processes can build
on that input flow and the tested result lifecycle. Map each algorithm to the
available Rasterio/Python capabilities. Add Shapely/Pyogrio/GeoPandas when an
implemented operation needs them. Do not add an engine plugin framework.

Preserve the four tested warp response combinations, default value transmission,
expiry, capacity controls and independent-client download checks when adding
another file-producing operation. No additional operation or asynchronous
infrastructure is part of the completed warp scope. See the
[historical Terrio warp report](docs/warp-milestone.md) and
[current pivot validation](docs/rasterio-pivot.md#validation-status).

Track conformance gaps alongside usability. Raster source references and binary
values are supported, but scalar CRS/resampling references, full Core job
resources and Annex A coverage remain unresolved. The published binary-schema
overlap also affects inline requests. Keep future work distinct
from the current public capabilities and from historical checker/CITE evidence.

## Licence and origins

This service reuses integration, testing and deployment infrastructure from the
MIT-licensed [bkn-terrain-processes](https://github.com/Gouwe-Gozer/bkn-terrain-processes).
The original notices and the copyright for Minnert Wijnands (Gouwe-Gozer) remain
in [LICENSE](LICENSE); [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) records
origin attribution and dependency notices. Preserve these when reusing code.
The source was already copied into this repository; no separate predecessor
checkout is needed for routine work.

## Standards and upstream references

Use the normative [OGC API – Processes Part 1: Core 1.0.0](https://docs.ogc.org/is/18-062r2/18-062r2.html),
especially sections 7.4, 7.9–7.13, 8 and 10, and
[Annex A](https://docs.ogc.org/is/18-062r2/18-062r2.html#_abstract_test_suite).
The [OGC review guide](docs/validation.md#ogc-review-guide) maps these to local
tests and distinguishes implemented behavior from remaining conformance work.
The [official schemas](https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi/schemas/)
and [JSON examples](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/)
serve different purposes: examples are not schemas. Offline schema fixtures
live under `tests/schemas/ogc-processes-1.0`.

- [pygeoapi](https://github.com/geopython/pygeoapi) and its [0.24.0 release](https://github.com/geopython/pygeoapi/releases/tag/0.24.0)
- [Rasterio](https://rasterio.readthedocs.io/en/stable/) and [NumPy](https://numpy.org/doc/stable/)
