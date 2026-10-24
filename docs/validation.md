# Validation and standards

The normative reference is [OGC API – Processes Part 1: Core 1.0.0][processes-core]
(18-062r2), including [Annex A][abstract-tests]. Use the official
[schemas][official-schemas] to validate documents; the official
[ProcessDescription.json][process-example] and [Execute.json][execute-example]
illustrate representations and are not schemas. The unchanged
[offline snapshot](../tests/schemas/ogc-processes-1.0/README.md) supports deterministic tests.

## Conformance claims and gaps

`/conformance` advertises Processes Core, JSON, OpenAPI 3.0 and OGC Process
Description, plus upstream Common/HTML discovery classes. It omits Callback,
Job List and Dismiss. The [Core audit](core-conformance-audit.md) reviews
Requirements 1–46 for the public synchronous profile and maps them to tests.

The confirmed gaps are corrected: raster/scalar references use shared bounded
HTTPS resolution, job errors expose the prescribed URI in JSON/HTML, existing
job routes are described, and discovery has required relations and usable paging.
The public manager retains no jobs, as permitted for synchronous execution.
Conditional requirements for repeated/object/bbox/mixed inputs, multiple outputs
and async execution must be reassessed when those capabilities are introduced.

The audit and regressions establish the recorded behavior, not a certificate or
a new full TEAM Engine assessment. The published binary-schema overlap below
remains explicit. The static checker retains reviewed expectations for unreachable
job-success/async responses and optional Job List support; no fake success
responses or substitute job system were added to remove those findings.

The application `/results/<id>/output.tif` route is an output-reference target,
not `/jobs/{jobID}/results`. A future reusable-upload endpoint would also be an
extension, not evidence of Core conformance.

## OGC review guide

| Review area | Standard pointer | Evidence or limitation |
| --- | --- | --- |
| Discovery and claims | Sections 7.4, 7.9–7.10 | HTTP and official-schema tests; scoped Core audit above |
| Operation descriptions | Section 8, Requirements 49–51 | [Value/wire distinction](inputs.md#ogc-scope-and-deployment), independent contracts and `test_ogc_schemas.py` |
| Input delivery/validation | Section 7.11.2, Requirements 18, 20, 22, 24 | [Input policy](inputs.md), raster/scalar/JSON references, qualified GeoJSON objects and inline tests |
| Execution preferences/defaults | Section 7.11.2, Requirements 25–27 | Info/warp HTTP tests; synchronous execution only |
| Synchronous results | Section 7.11.4, Requirements 28, 30, 32 | [Four file-result response modes](results.md#http-contract), TIFF/GeoJSON documents and independent downloads |
| Multiple raw outputs | Section 7.11.4, Requirements 29, 31 | Multipart delivery not implemented |
| Job resources | Sections 7.12–7.13; Permission 7 | Existing routes return the required unknown-job errors and are documented; no retained synchronous jobs |
| OpenAPI/exceptions | Section 10; Requirement 15 for unknown processes | [Catalogue](errors.md), generated definition and actual JSON exception/schema tests |
| Conformance assessment | Annex A | Partial evidence; no current-service certification |

For contract changes, review the relevant clauses and official examples, then
keep process descriptions, request validation, generated OpenAPI and executable
examples consistent. Check pixels, CRS, transforms, nodata and allocation limits
as well as HTTP statuses, headers and representations. Test reference acquisition
and delivery independently, including policy failures, cleanup and expiry.
Follow [adding a process](adding-a-process.md) and run the
[development checks](development.md). Review checker changes before updating a
baseline; preserve known schema limitations rather than modifying official fixtures.

## Published binary-schema limitation

The unchanged `inputValueNoObject.yaml` uses `oneOf` with an unrestricted string
and a byte-formatted string. Valid base64 matches both, so strict validation
rejects inline binary values even with a base64 format checker. Tests record the
overlap for requests/results. The official examples use base64 with `encoding`
and `mediaType`, as our qualified inline representation does.

Discovery, reference requests, exceptions and reference result documents are
validated against the official snapshot. Inline binary requests/responses use
application schemas plus actual GeoTIFF decoding. No official schema fixture is
modified to hide the overlap; these checks do not establish complete conformance.

## Test and checker coverage

- Adapter tests inspect actual Rasterio pixels, metadata, masked statistics,
  dimensions, transforms, nodata and bounds, including all offered warp choices.
- HTTP/schema tests cover discovery, defaults, four warp modes, typed/sanitized
  errors, unsupported requests and downloads. Input tests use local TLS to check
  verified/pinned connections, redirects, limits, deadlines and cleanup.
- Storage tests cover quota, expiry, locking, atomic delivery and safe paths.
  Startup tests cover effective settings and preserve existing result data.
- The local-file client has an end-to-end HTTP test plus checks for preserved
  destinations and discarded failed downloads. These tests do not validate the
  external browser client; track it in [the interoperability log](client-interoperability.md).
- Release smoke checks run processing through Gunicorn, download/open results
  from independent clients, inspect isolation and verify restart persistence.
- [Geonovum 1.2.0](../validation/geonovum/README.md) checks OpenAPI statically.
  Its eight reviewed diagnostics are retained explicitly (including one
  conditional async-201 expectation per synchronous process).
- [CITE/TEAM Engine evidence](../validation/cite-teamengine/README.md) concerns
  the predecessor's integration-only echo fixture. No current raster-service
  TEAM Engine run or certification is claimed.

## Recorded checks

These are dated observations, not permanently current test counts or guarantees:

- Raster operations, **2026-10-24**: **484 tests passed**, **95.34% coverage**.
  Sampling, classification and polygonization cover HTTPS/inline inputs, band
  selection, CRS handling, Point/MultiPoint/FeatureCollection sampling, all four
  TIFF/GeoJSON delivery modes, downloads,
  limits and errors. Quality/pre-commit, configuration/OpenAPI and release
  isolation checks pass. Host and separate client-container smoke checks pass;
  stored TIFF and GeoJSON downloads survive restart. The eight-finding Geonovum baseline
  adds only one conditional async expectation per new process. External client
  GeoJSON UI behavior remains untested.

- Core audit, **2026-10-24**: **401 tests passed**, **95.40% coverage**, including
  real TLS scalar/raster references and compatibility with the existing async
  manager. Quality, configuration/OpenAPI and release checks pass. The checker
  baseline's exact two-finding replacement was reviewed; see [the audit](core-conformance-audit.md).

- Documentation audit, **2026-10-24**, code at `e8c5dc3`: **360 tests passed**,
  **95.15% application coverage**, against the existing 70% floor. The upstream
  Pydantic class-configuration deprecation warning remains.
- Service usability checkpoint `8efb5d5`, **2026-10-24**: quality and
  public/integration configuration/OpenAPI checks passed. The self-contained
  release passed startup, local-file processing, independent multiband input,
  all warp modes and isolation. Invalid result-count/host settings stopped the
  entrypoint before Gunicorn. Node 24/npm 11.6.0 retained the Geonovum baseline.
- Earlier user-input validation, **2026-10-24**: host and separate-container
  clients processed an independent two-band UInt16 raster; a public HTTPS check
  used GDAL's `byte.tif` without redistributing it. Issued results survived service
  recreation/restart, and input workspaces were removed after handled requests.
- A recorded 512 by 512 Float32 DEM check produced a 910,778-byte input and
  910,911-byte output. Local HTTP info/warp took about 0.043/0.063 seconds; the
  container memory peak rose from about 297 to 304 MiB under its 512 MiB limit.
  Pixels matched independent reprojection within tolerance. These single-machine
  observations were not rerun for this documentation audit and are not worst-case
  bounds or throughput claims.

Use the development commands and CI for fresh results. Older backend checkpoints
are summarized in [migration](migration.md), [warp](warp-milestone.md) and the
[backend decision](rasterio-pivot.md); their full records remain in Git history.

[processes-core]: https://docs.ogc.org/is/18-062r2/18-062r2.html
[abstract-tests]: https://docs.ogc.org/is/18-062r2/18-062r2.html#_abstract_test_suite
[official-schemas]: https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi/schemas/
[process-example]: https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/ProcessDescription.json
[execute-example]: https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/Execute.json
