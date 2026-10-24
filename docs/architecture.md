# Architecture

pygeoapi supplies discovery, Flask routes, configuration and process registration.
Each public processor validates its operation's inputs/output choices, calls a
small Rasterio/GDAL adapter and owns its result representations. NumPy supplies
masked statistics; [raster metadata](raster-info.md) is an application-owned contract.

## Module boundaries

| Location | Responsibility |
| --- | --- |
| `config/pygeoapi.yml` | Explicit public process and synchronous manager registration |
| `contracts/info.py`, `contracts/warp.py` | Independent operation descriptions and executable schemas |
| `contracts/sources.py` | Binary raster value schema and supported execution representations |
| `processes/info.py`, `processes/warp.py` | Per-operation validation, adapter calls and output formatting |
| `engine.py` | Raster validation, metadata/statistics and bounded reprojection; no pygeoapi imports |
| `inputs.py` | Controlled HTTPS/base64 acquisition, private staging and cleanup |
| `storage.py` | Bounded GeoTIFF publication, locking, expiry and cleanup |
| `manager.py` | Synchronous execution, typed exceptions and delegated representations |
| `responses.py` | Explicit response body, media type, status and headers |
| `app.py` | Flask request guard, JSON exception normalization and result downloads |
| `errors.py` | JSON exception URI catalogue and compatible legacy fields |
| `startup.py` | Runtime settings, directory probes and effective configuration summary |
| `openapi.py` | Version-checked corrections to upstream OpenAPI generation |
| `datasets.py`, `data/` | Bundled fixture submitted as ordinary raster data by tests/smoke clients |

Paths above are relative to `src/geo_processes/` unless otherwise stated.

## Execution and data lifecycle

The required `source` accepts controlled HTTPS or inline base64. The resolver
stages a private local file and validates it before the adapter runs; client
URLs never become GDAL inputs. Only GTiff is enabled for source reads, with
internal georeferencing, sidecars/PAM disabled and PROJ networking off.
Input lifetime and output retention are independent; see [input policy](inputs.md).

Info computes exact finite masked statistics, including defined null/non-finite
nodata representations. Warp requires a source CRS and retains source dimensions
to bound allocation. Supported operation parameters live in their contracts;
adding more CRSs or algorithms requires validation and meaningful raster tests.

`OgcSynchronousManager` delegates `format_result()` to each processor and accepts
`ProcessResponse` for native bytes or explicit headers/status. It does not assume
particular output identifiers or counts. Multipart output and job infrastructure
are not implemented. File results are atomically published under opaque IDs;
[storage](results.md) supplies expiry and cross-worker locking.

The owned entrypoint runs the startup preflight, generates OpenAPI and launches
Gunicorn. Importing the Flask application also validates runtime settings. See
[development](development.md#startup-validation) and [release deployment](release-image.md).

## Compatibility corrections

Regression tests retain the following corrections for pygeoapi 0.24.0:

- A boundary guard rejects malformed execute shapes before upstream dereferences them.
- The manager corrects document wrapping, preserves typed failures, sanitizes
  unexpected exceptions and removes the unsupported Callback claim.
- A private manager-to-Flask marker selects HTTP 204 for raw/reference results;
  it is removed before delivery. Known JSON exceptions use the [catalogue](errors.md).
- The OpenAPI generator corrects discovery schemas, limits, error responses and
  execution choices. Process metadata is copied before upstream can mutate it.

These are covered by manager, HTTP, schema and OpenAPI tests. Reassess them on
an upstream upgrade; no upstream source or entrypoint is patched. Remaining
conformance gaps are tracked in [validation](validation.md).

## Extension boundaries

Give each new operation its own adapter, processor and contract, following the
[contribution recipe](adding-a-process.md). Extract shared GeoTIFF delivery when
another file-producing operation demonstrates the duplication. Formatting still
lives in the warp processor, and the download route's OpenAPI registration is
currently conditional on `raster-warp`; do not mistake that coupling for a
requirement that every future operation use the same output ID.

`scripts/process_raster.py` is a user-facing example client. Smoke scripts cover
all supported representations for developer checks. Historical implementation
and naming decisions are separate from these maintained module boundaries.
