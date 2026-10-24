# Architecture

pygeoapi supplies discovery, Flask routes, configuration and process registration.
Each public processor validates its operation's inputs/output choices, calls a
small Rasterio/GDAL adapter and owns its result representations. NumPy supplies
masked statistics; [raster metadata](raster-info.md) is an application-owned contract.

## Module boundaries

| Location | Responsibility |
| --- | --- |
| `config/pygeoapi.yml` | Explicit public process and synchronous manager registration |
| `contracts/<operation>.py` | Independent operation descriptions and executable schemas |
| `contracts/files.py` | Small schema builders for the repeated file-result contract |
| `contracts/sources.py` | Binary raster value schema and supported execution representations |
| `processes/<operation>.py` | Independent BaseProcessor implementations, parameter checks and adapter calls |
| `processes/common.py` | Narrow integer/band checks and typed error mapping for the new operations |
| `engine.py` | Raster validation, metadata/statistics and bounded reprojection; no pygeoapi imports |
| `operations/` | Point sampling, range classification, polygonization and bounded GeoJSON serialization |
| `inputs.py` | Controlled HTTPS/base64 acquisition, private staging and cleanup |
| `storage.py`, `delivery.py` | TIFF/GeoJSON publication, shared expiry/quotas and OGC file-result formatting |
| `manager.py` | Synchronous execution, typed exceptions and delegated representations |
| `responses.py` | Explicit response body, media type, status and headers |
| `app.py` | Flask request guard, JSON exception normalization and result downloads |
| `errors.py` | Exception catalogue and API-instance JSON/HTML renderer, including job errors |
| `discovery.py` | Required landing links and traversable process lists, independent of the manager |
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
  it is removed before delivery. A renderer on the configured API instance uses
  the [catalogue](errors.md) for JSON/HTML errors with either job manager.
- Discovery adds the required OGC landing relation and working pagination while
  retaining upstream metadata generation and HTML templates.
- The OpenAPI generator corrects discovery schemas, limits, error responses and
  execution choices. Process metadata is copied before upstream can mutate it.
- `logging_filters.py` filters only Babel unknown-locale warnings from
  `pygeoapi.l10n.str2locale` whose identifiers match registered schema, example
  or link keys. Upstream's silent metadata probes still log failures in 0.24.0;
  there is no separate probe logging setting. Python's logger filter extension
  keeps the translator, metadata, configured log level and other diagnostics
  intact. New process data keys are collected automatically at application startup.

These are covered by manager, HTTP, schema and OpenAPI tests. Reassess them on
an upstream upgrade; no upstream source or entrypoint is patched. Remaining
conformance gaps are tracked in [validation](validation.md).

## Extension boundaries

Give each new operation its own adapter, processor and contract, following the
[contribution recipe](adding-a-process.md). Warp and the three new operations
reuse a file formatter with explicit output ID, media type and transmission.
Storage accepts only the two implemented extensions. Each file processor declares
`result_extension` so its download route appears in OpenAPI even without warp.
This is a small shared delivery helper, not an engine registry or processor base
class; independent processors still subclass pygeoapi's `BaseProcessor` directly.

The pinned upstream processor/manager interfaces were checked before this
extraction. pygeoapi supplies registration, routing and execution dispatch; its
stock manager does not supply our expiring non-job downloads or OGC result
mapping. The existing formatter hook is reused, with no new manager coupling or
job lifecycle. GeoJSON uses Rasterio/GDAL and the standard library; no vector
library, driver plugin or asynchronous machinery is introduced.

`scripts/process_raster.py` is a user-facing example client. Smoke scripts cover
all supported representations for developer checks. Historical implementation
and naming decisions are separate from these maintained module boundaries.
