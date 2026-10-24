# Adding a raster process

Give each operation a clear contract and a small Rasterio adapter. Follow
`raster-info` for JSON results and `raster-warp` for a file result. Register a
process explicitly; the present two operations do not need an auto-discovery
system or a generalized engine plugin layer.

## 1. Define the operation and its bounds

Write down the inputs, defaults, supported CRSs/units, output identifiers,
formats and transmission modes before implementing the algorithm. For example,
a future clip operation would need an explicit bounding-box CRS, coordinate
order, behavior outside the source extent and an output-pixel budget. This is
a design example, not an implemented capability.

Decide which validation can run before acquiring input or creating an output.
Account for bands, decoded blocks and all simultaneous inputs/outputs, including
compressed TIFFs. Keep the current input/result limits unless measured evidence
supports a change. Avoid accepting arbitrary GDAL options or driver names.

## 2. Add the contract, adapter and processor

| Location | What to add |
| --- | --- |
| `src/geo_processes/contracts/<operation>.py` | Process metadata, input/output value schemas and the supported execute/response contracts |
| `src/geo_processes/engine.py`, or a small operation module | Plain Python/Rasterio function with no pygeoapi imports; explicit parameters and application-owned return values |
| `src/geo_processes/processes/<operation>.py` | Independent `BaseProcessor` subclass; copy metadata, validate inputs/output options, call the adapter and format results |
| `config/pygeoapi.yml` | Explicit resource ID, `type: process` and dotted processor class name |
| `tests/` and `examples/` | Meaningful raster/HTTP tests and an ordinary execution request |

Reuse `contracts/sources.py` for GeoTIFF value and wire conventions, and
`inputs.resolve_source()` for acquisition, validation and cleanup. The processor
must validate supported source forms before processing. Use `require_crs=True`
when the operation needs georeferencing. Do not reopen a client-supplied URL
through Rasterio or accept server filesystem paths.

For file results, use `ResultStore.publish()` and its existing lifetime/quotas.
Return a `ProcessResponse` where native bytes, headers or a 204 are needed.
Give the operation its own `format_result()` and `openapi_execution()` when
appropriate. Shared code must preserve explicit output identifiers, supported
media types and transmission modes; it must not assume one JSON output.
Extract a helper only when a second real implementation makes duplication clear.

Use the typed request/input exceptions in `manager.py` for controlled client
errors, and sanitized `ProcessorExecuteError(user_msg=...)` for internal failures.
Map additional cases deliberately into the [exception catalogue](errors.md).
Do not return internal exception strings or turn storage failures into 400s.

## 3. Review the OGC contract

Use the [OGC review guide](validation.md#ogc-review-guide), the normative
[Part 1 standard](https://docs.ogc.org/is/18-062r2/18-062r2.html) and official
[ProcessDescription.json](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/ProcessDescription.json)
and [Execute.json](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/Execute.json)
examples together:

- Describe input **values** in Process Description schemas (Requirements 49–51),
  including media type/encoding for binary data. HTTPS references and inline
  transport are execute representations (Requirements 18 and 22), not separate
  raster value types. Keep demo identifiers out of the public schema.
- Set occurrence counts and defaults deliberately. Define raw/document behavior,
  supported formats and value/reference transmission per output. Advertise only
  what the implementation accepts; do not inherit async/callback capabilities.
- Check generated OpenAPI against the real HTTP contract. If a new file operation
  needs the existing result route, extend its OpenAPI registration deliberately;
  it is currently registered when `raster-warp` is present.

Scalar input references, Core job resources and the published binary execute
schema overlap remain documented gaps. Adding an operation does not resolve
them or establish certification.

## 4. Verify and document the behavior

- Check pixels, CRS, transform, nodata/masks and dimensions with small synthetic
  rasters, including relevant invalid and allocation-limit cases.
- Exercise actual HTTP discovery and execution, each advertised output mode,
  sanitized failures and input/output cleanup. Download reference results through
  HTTP and open them independently. Avoid tests that only compare copied metadata.
- Use `validate_official()` from `tests/test_ogc_schemas.py` for process descriptions,
  exceptions and applicable execute/results documents. Keep the official schema
  fixtures unchanged and distinguish their known limitations from service defects.
- Run the [development checks](development.md), validate configuration/OpenAPI,
  and run container smoke checks if startup, dependencies or delivery change.
  Review checker differences before changing a conformance baseline.
- Update README/examples, relevant operation documentation, the roadmap and
  `CODEX_HANDOVER.md` with implemented behavior and evidence. Add direct dependency
  declarations and the lockfile together only when the operation actually needs
  a new library. Preserve licences/notices for reused code and data.
