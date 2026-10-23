# terrio-processes — current handover

`terrio-processes` exposes bounded Terrio operations through OGC API – Processes
using the official pygeoapi package. Maintainer: Minnert Wijnands (Gouwe-Gozer).
The first milestone, `terrio-info`, is implemented. See [README](README.md) for
usage and [development](docs/development.md) for setup and checks.

## Current implementation

- Python 3.12, pygeoapi **0.24.0** and Terrio **0.4.2**, with project-local
  dependencies managed by `uv` and pinned in `uv.lock`.
- One public process: **`terrio-info`**. Its required `source` input is the
  inline string `demo-dem`, mapped to a bundled 4 by 3 GeoTIFF in EPSG:28992.
  Clients cannot choose filesystem paths, URLs or arbitrary Terrio options.
- The plain Python adapter calls `terrio.info(path, stats=True)` directly.
  Each processor owns its input validation, description and result formatting.
- Synchronous execution only: `jobControlOptions: ["sync-execute"]`,
  `outputTransmission: ["value"]`. Omitted `response` means `raw`; omitted
  `outputs` selects the defined output; omitted transmission means `value`.
- Raw execution returns native raster information with HTTP 200 and
  `application/json`. Document execution returns HTTP 200 and
  `{"info":{"value":{...raster information...}}}`. `Prefer: respond-async`
  remains synchronous and does not advertise a job URL.
- Unknown inputs/outputs, unsupported formats/transmission, callbacks and
  malformed requests are rejected with JSON client errors. Engine failures
  return sanitized server errors.
- Docker uses the pinned official pygeoapi image and installs Terrio in the
  same `/venv` used by Gunicorn. Release Compose retains non-root execution,
  a read-only root, bounded `/tmp`, dropped capabilities and no-new-privileges.

## Code and validation map

| Location | Responsibility |
| --- | --- |
| `src/terrio_processes/engine.py` | Terrio adapter without pygeoapi imports |
| `src/terrio_processes/processes/info.py` | Process validation and output representation |
| `src/terrio_processes/contracts/info.py` | Dataset registry, metadata and schemas |
| `src/terrio_processes/app.py` | Boundary validation for registered execution routes |
| `src/terrio_processes/manager.py` | Synchronous execution and typed/sanitized errors |
| `src/terrio_processes/openapi.py` | Version-checked corrections to upstream OpenAPI |
| `config/pygeoapi.yml` | Public resource and manager registration |
| `docker/`, `compose*.yml` | Application startup and deployment configurations |
| `tests/`, `scripts/`, `.github/workflows/ci.yml` | Unit, official-schema, HTTP, quality and container checks |

Keep the tested compatibility corrections until equivalent HTTP tests establish
that upstream handles them. The pinned DummyManager's document wrapper and
exception handling, malformed execute shapes, unconditional Callback claim,
generated discovery/execution schemas and metadata mutation still need the
current corrections. No upstream Python source or entrypoint is patched.

The integration-only `async-echo`/TinyDB configuration is a diagnostic fixture,
not a public capability. The pinned Geonovum checker has four recorded job/async
diagnostics. Historical CITE results describe the predecessor service, not this
implementation. See [validation](docs/validation.md) for the evidence boundary
and [migration report](docs/migration.md) for the initial compatibility inventory.

## Working rules

Follow [AGENTS.md](AGENTS.md). Use user-installed `uv`, a local `.venv` and
`uv run` for Python commands. Preserve Ruff, Bandit, pytest/coverage,
pre-commit and CI; keep dependency and lockfile changes together. Inspect the
Python constraints and compatibility before changing the interpreter.

Keep operations independent and narrowly defined. Shared infrastructure must
not assume that every future process has one JSON output or value transmission.
Do not add a generic engine plugin system, a GDAL backend, asynchronous jobs or
arbitrary remote data access as incidental work on the current milestone.
Do not commit, push or publish unless the user requests it.

## Next milestone: file-producing processing

`terrio-warp` is the next separate milestone; `terrio-hillshade` can follow.
Before implementing either, decide and test:

1. Safe input handling. External OGC `href` inputs need protocol/destination
   restrictions, redirect handling, timeouts, size limits and content validation.
2. Bounded writable output storage, per-request filenames and retention/cleanup
   compatible with the hardened release container.
3. A client-retrievable HTTP URL and the supported output transmission modes.
   A container path or an internal hostname is not a downloadable result.
4. Standards-correct responses: document/reference is an output-ID mapping
   containing `href` and media type; raw/reference, if offered, requires HTTP 204,
   an empty body and `Link` headers. Value transmission remains the default.
5. End-to-end download/open tests from another client and resource limits
   appropriate to synchronous execution. Advertise new capabilities only after
   their behavior is implemented and tested.

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
especially sections 7.10–7.11, section 8 and [Annex A](https://docs.ogc.org/is/18-062r2/18-062r2.html#_abstract_test_suite).
The [official schemas](https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi/schemas/)
and [JSON examples](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/)
serve different purposes: examples are not schemas. Offline schema fixtures
live under `tests/schemas/ogc-processes-1.0`.

- [pygeoapi](https://github.com/geopython/pygeoapi) and its [0.24.0 release](https://github.com/geopython/pygeoapi/releases/tag/0.24.0)
- [Terrio](https://github.com/opengeos/terrio) and its [Python API](https://terrio.opengeos.org/python/)
