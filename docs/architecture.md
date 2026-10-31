# Architecture

pygeoapi supplies discovery, Flask routes, configuration and process registration.
Each public processor validates its operation's inputs/output choices, calls a
small Rasterio/GDAL adapter and owns its result representations. NumPy supplies
masked statistics; [raster metadata](raster-operations.md#raster-information--raster-info) is an application-owned contract.

## Module boundaries

| Location | Responsibility |
| --- | --- |
| `config/pygeoapi.yml` | Public process registration and default durable manager; explicit synchronous override |
| `contracts/<operation>.py` | Independent operation descriptions and executable schemas |
| `contracts/files.py` | Small schema builders for the repeated file-result contract |
| `contracts/sources.py` | Binary raster value schema and supported execution representations |
| `processes/<operation>.py` | Independent BaseProcessor implementations, parameter checks and adapter calls |
| `processes/common.py` | Narrow integer/band checks and typed error mapping for the new operations |
| `engine.py` | Raster validation, metadata/statistics and bounded reprojection; no pygeoapi imports |
| `operations/` | Point sampling, range classification, polygonization and bounded GeoJSON serialization |
| `inputs.py` | Controlled HTTPS/base64 acquisition, private staging and cleanup |
| `storage.py`, `delivery.py` | TIFF/GeoJSON publication, shared expiry/quotas and OGC file-result formatting |
| `manager.py` | Synchronous execution and delegated representations |
| `async_manager.py`, `worker.py`, `jobs.py` | Default PostgreSQL-backed handoff, independent bounded worker and stored-response HTTP adapter |
| `responses.py` | Explicit response body, media type, status and headers |
| `app.py` | Flask request guard, JSON exception normalization and result downloads |
| `errors.py` | Shared execution exceptions, catalogue and API-instance JSON/HTML renderer |
| `discovery.py` | Required landing links, process-list paging and configuration-scoped capability corrections |
| `startup.py` | Runtime settings, directory probes and effective configuration summary |
| `openapi.py` | Version-checked corrections to upstream OpenAPI generation |
| `documentation.py`, `templates/openapi/redoc.html` | Supported template override for the pinned ReDoc presentation; other templates fall back to pygeoapi |
| `datasets.py`, `data/` | Internal demo fixture plus public point/polygon/raster samples |

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
particular output identifiers or counts. The five production processes each have
one output; custom processors can supply multipart through their formatter, as
the validation-only echo does. There is no automatic multipart builder. Durable jobs use the same
execution/formatting method in a separate worker; see [async execution](asynchronous-execution.md). File results are atomically published under opaque IDs;
[storage](results.md) supplies expiry and cross-worker locking.

Rasterio datasets are opened within each operation's context managers and never
shared across executions. Input slots are locked for their full lifetime;
output publication uses a separate writer lock and unique temporary directories.
The separate async worker preserves these isolation rules.

The owned entrypoint runs the startup preflight, generates OpenAPI and launches
Gunicorn. Importing the Flask application also validates runtime settings. See
[development](development.md#startup-validation) and [release deployment](release-image.md).

## Compatibility corrections

Regression tests retain the following corrections for pygeoapi 0.24.0:

- A boundary guard rejects malformed execute shapes before upstream dereferences them.
- Execution JSON uses Jinja2's existing HTML-safe JSON encoder, preserving decoded
  values while emitting Unicode escapes for HTML delimiters. pygeoapi 0.24.0's
  synchronous serializer substitutes HTML entities; a request-local API/manager
  copy captures the original formatted value and re-encodes it before Flask
  compression. Upstream still owns execution negotiation, headers and failures.
  Async persistence reuses pygeoapi's type conversion with `allow_nan=False`;
  result retrieval uses the same HTML-safe encoder. Native file/text responses, HTML
  templates and upstream's global serializer are unchanged; parsed data remains
  untrusted and templates retain their normal escaping.
- The manager corrects document wrapping, preserves typed failures, sanitizes
  unexpected exceptions and rejects unsupported subscribers. Shared request/input
  exceptions live in `errors.py`, so processors and delivery do not import the manager.
- A private manager-to-Flask marker selects HTTP 204 for raw/reference results;
  it is removed before delivery. A renderer on the configured API instance uses
  the [catalogue](errors.md) for JSON/HTML errors with either job manager.
- Discovery adds the required OGC landing relation and working pagination while
  retaining upstream metadata generation and HTML templates.
  JSON-LD keeps pygeoapi's native DataCatalog body and receives HTTP Link
  headers; only ordinary JSON landing documents receive a body link.
  Callback declarations follow the API instance manager's native
  `supports_subscribing` capability, independently of `is_async`. Constructing
  our manager does not modify pygeoapi's global conformance declarations.
  Job List follows the durable manager's `supports_job_list` flag. Its narrow
  `get_jobs` override adds bound SQL filters, retention and pagination to the
  existing PostgreSQL table; upstream 0.24.0 ignores limit/offset there.
  `jobs.py` shares the individual-job status serializer and upstream HTML template.
  Job List requires `processID` in acceptance/status documents; the existing
  request-local HTTP adapter adds it to upstream's 201 body. No new table,
  lifecycle state or processor coupling is introduced.
- The OpenAPI generator corrects discovery schemas, limits, error responses and
  execution choices. Process metadata is copied before upstream can mutate it.
- Read-only feature providers do not inherit the unsupported Features CRUD claim.
  When all providers are read-only GeoJSON, discovery also omits CQL2 claims:
  this provider ignores parsed CQL filters. A request guard rejects such queries,
  and OpenAPI omits their query POSTs. Native collection reads remain upstream;
  conformance corrections use the API instance and original HTML template rather
  than changing upstream global declarations.
- `logging_filters.py` filters only Babel unknown-locale warnings from
  `pygeoapi.l10n.str2locale` whose identifiers match registered schema, example
  or link keys, or literal processor configuration keys used by HTML templates.
  Upstream's silent metadata probes still log failures in 0.24.0;
  there is no separate probe logging setting. Python's logger filter extension
  keeps the translator, metadata, configured log level and other diagnostics
  intact. New process data keys are collected automatically at application startup.
- The default ReDoc template is overridden through pygeoapi's existing template
  path setting. ReDoc 2.5.3 is pinned because the upstream classic script tag is
  incompatible with the ES-module bundle now served by `redoc@latest`. Explicit
  operator template paths are preserved; other templates use upstream fallback.

These are covered by manager, HTTP, schema and OpenAPI tests. Reassess them on
an upstream upgrade; no upstream source or entrypoint is patched. Remaining
conformance gaps are tracked in [validation](validation.md).

## Extension boundaries

Public samples use native GeoJSON feature providers and Flask's static-file
blueprint. Feature discovery, paging, IDs and bbox queries remain upstream;
there is no application-owned Features implementation. Small compatibility
corrections omit empty property-selection enums and set the GeoJSON media type
for successful feature responses. Native Features schemas validate these routes.
See [sample data](sample-data.md) for provenance, paths and processing examples.

Give each new operation its own adapter, processor and contract, following the
[contribution recipe](adding-a-process.md). The four file-producing operations
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
processing library or driver plugin is introduced by these operations.

`scripts/process_raster.py` is a user-facing example client. Smoke scripts cover
all supported representations for developer checks. Keep dated investigations separate from maintained module boundaries.
