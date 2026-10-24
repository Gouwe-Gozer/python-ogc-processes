# Future work

The goal is a ready-to-use API for **users' own rasters**, with a growing catalogue
of useful operations. HTTPS and inline base64 input, information/reprojection,
sampling, reclassification, polygonization, downloadable results and the local-file example are implemented; see
[README](../README.md), [inputs](inputs.md) and [results](results.md).
The items below are proposals or unresolved decisions, not advertised capabilities.

## Raster operations and CRS coverage

- Add operations driven by concrete needs: cropping, resampling, band selection
  and hillshade are candidates. Confirm each algorithm's implementation rather
  than assuming every GDAL function has a direct Rasterio equivalent.
- Expand the target EPSG list with representative transformation tests in the
  local and release environments, including required offline transformation
  resources. The three current targets are an API policy in `contracts/warp.py`,
  not separate process implementations.
- Add target resolution/extent controls only with an output-pixel budget checked
  before allocation. More file bytes alone are not a sufficient resource budget.
- Reuse the shared input/result lifecycle and TIFF/GeoJSON delivery helpers,
  preserving explicit output IDs and formats.
  Follow [adding a process](adding-a-process.md); keep registration explicit.

## Pilot and client workflow

- Expand suitably licensed, small DEM/imagery fixtures across data types, bands,
  nodata and CRSs. Keep CI independent of public raster downloads.
- Measure runtime, memory and output size before raising existing limits. Current
  workload observations are in [validation](validation.md#recorded-checks).
- Complete the external client's file/URL and result-handling workflow, using
  the [interoperability log](client-interoperability.md) to distinguish observed
  defects from unverified behavior. Client changes belong in its own repository.
- Decide whether repeated processing needs reusable input uploads/storage.
  That extension needs explicit access, privacy, expiry and combined-input budgets.

## Standards and deployment decisions

The [Core audit](core-conformance-audit.md) records corrected input-reference,
job-error, OpenAPI and discovery behavior, with applicability for Requirements
1–46. Revisit conditional rows when adding input/output types or execution modes.
An external conformance assessment remains separate from these regression tests.

Async execution is a later workload decision. The audit documents why the
existing TinyDB diagnostic is not a configuration-only replacement for raster
execution, and which fixes already work with either manager. Persistent jobs
for synchronous runs remain optional; do not add artificial job state or success
responses solely to silence conditional checker findings.

Before sharing a hosted service, choose users/access control, input/result
visibility, TLS, logging and storage maintenance. Queuing, asynchronous workers,
object storage and distributed coordination should follow measured workload
needs. Current deployment boundaries are in [release deployment](release-image.md).

Vector operations may introduce Shapely, Pyogrio or GeoPandas when a concrete
operation requires them. Declare directly used dependencies explicitly and keep
contracts application-owned. An operator dataset catalogue remains an optional
convenience; it is not a prerequisite for processing users' data.
