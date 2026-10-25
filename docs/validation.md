# Validation and standards

The normative reference is [OGC API – Processes Part 1: Core 1.0.0][processes-core]
(18-062r2), including [Annex A][abstract-tests]. Use the official
[schemas][official-schemas] to validate documents; the official
[ProcessDescription.json][process-example] and [Execute.json][execute-example]
illustrate representations and are not schemas. The unchanged
[offline snapshot](../tests/schemas/ogc-processes-1.0/README.md) supports deterministic tests.

## Conformance claims and gaps

`/conformance` advertises Processes Core, JSON, OpenAPI 3.0 and OGC Process
Description, plus inherited Common and read-only Features classes. It omits Callback,
Job List and Dismiss. The [Core audit](core-conformance-audit.md) reviews
Requirements 1–46 for the public synchronous profile and maps them to tests.

Callback filtering is local to the API instance and follows its manager's native
`supports_subscribing` capability, not `is_async`. Tests cover independent API
instances and both capability values with sync/async managers in JSON and HTML.
Manager construction leaves the upstream conformance list unchanged; the public
manager's Callback claim remains absent.

The pre-stabilization declarations are captured in the dated CITE proposal's
[`discovery.json`](../validation/cite-teamengine/current/discovery.json).
The Processes suite does not validate inherited Features/CQL2 classes.
The service now excludes the unsupported Features `create-replace-delete` claim
when no feature provider is editable. It also excludes Basic CQL2/CQL2 text when
all configured providers are read-only GeoJSON: that provider ignores CQL filters.
Such queries now return 400, and the generated OpenAPI omits their query POSTs.
Native bbox, paging and feature-ID reads remain available. The historical CITE
snapshot is unchanged; use the live `/conformance` for current declarations.

The confirmed gaps are corrected: raster/scalar references use shared bounded
HTTPS resolution, job errors expose the prescribed URI in JSON/HTML, existing
job routes are described, and discovery has required relations and usable paging.
The public manager retains no jobs, as permitted for synchronous execution.
Qualified GeoJSON object inputs are covered by the current audit. Reassess
conditional requirements when adding new input types, repeated occurrences,
multiple outputs or asynchronous execution.

The audit and regressions establish the recorded behavior, not a certificate.
The [current CITE observation](../validation/cite-teamengine/current/README.md)
adds executable-suite evidence with explicit failures/skips and coverage limits. The published binary-schema overlap below
remains explicit. The static checker retains reviewed expectations for unreachable
job-success/async responses and optional Job List support; no fake success
responses or substitute job system were added to remove those findings.

The application `/results/<id>/output.tif` route is an output-reference target,
not `/jobs/{jobID}/results`. A future reusable-upload endpoint would also be an
extension, not evidence of Core conformance.

### Inherited job routes in the synchronous profile

pygeoapi 0.24.0 registers `GET /jobs` independently of manager capabilities.
Its dummy manager (the base of our synchronous manager) returns an empty list,
so the route returns HTTP 200 with `jobs: []` before and after execution.
Upstream generates its OpenAPI entry only for an asynchronous manager. We retain
that behavior and keep `/jobs` outside the advertised synchronous contract;
Job List is an optional class, not claimed merely because this route responds.
This is inherited discoverability behavior, not evidence of retained or async jobs.

Unknown job status/results and `DELETE /jobs/{jobID}` return 404 with the
`no-such-job` type. Dismiss is not advertised either. Regression tests cover the
empty list, absent optional claims, sync preferences and these JSON/HTML errors.
We do not add successful job operations, fake records or new conformance claims
to reconcile the optional checker expectations. Client integrations should use
`jobControlOptions` and `/conformance` when determining job support.

## Repeatable commands

Install user-managed uv, Python 3.12, GNU Make and Docker Compose v2, then run
`uv sync --locked --all-groups`. External tool versions are pinned; network
access is needed for registry/schema downloads. No host Node, Java or Maven
installation is needed by the standard commands.

| Command | What it checks | API/report scope |
| --- | --- | --- |
| `make test` | Ruff, Bandit, pytest with coverage and configuration/OpenAPI validation | Our code and integration; XML reports in `runtime-data/validation/` |
| `make validate-geonovum` | Geonovum 1.3.2 static Processes 1.0.0 analysis, exact reviewed-baseline comparison | Running API at `127.0.0.1:5001`; raw JSON in `runtime-data/validation/geonovum.json` |
| `make validate` | Both commands above; excludes CITE | Requires the normal API running |
| `make validate-cite` | Official Processes ETS 1.3 with TEAM Engine 6.0.0-RC2 | Builds its own isolated real API; native reports, summaries and metadata in `runtime-data/cite/` |

Geonovum's eight-error report can match the reviewed baseline and return success;
that means no diagnostic regression, not full compliance. CITE remains strict:
its five recorded failures still produce a failed command. Infrastructure errors
are identified separately and never recorded as passing tests. Make itself wraps
unsuccessful commands in a nonzero status; the Python runners distinguish
conformance/baseline failure (1) from infrastructure failure (2).

Pull requests run the routine, release/runtime and Geonovum checks. CITE is an
explicitly triggered separate CI workflow and can also run locally without GitHub.
CI preserves reports even after failures. Neither runner automatically updates
reviewed baselines; inspect the actual tests, requirements and applicability
before proposing explicit tracked evidence changes.

[CITE instructions](../validation/cite-teamengine/README.md) cover CLI/REST,
manual browser fallback and cleanup. The [fresh baseline proposal](../validation/cite-teamengine/current/README.md)
classifies every failure and skip. The unchanged predecessor baseline is
historical. [Geonovum notes](../validation/geonovum/README.md) document the version,
locked runtime, diagnostic fields and review policy.

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
- [Geonovum 1.3.2](../validation/geonovum/README.md) checks OpenAPI statically.
  Its eight reviewed diagnostics are retained explicitly (including one
  conditional async-201 expectation per synchronous process).
- [CITE/TEAM Engine](../validation/cite-teamengine/README.md) now runs the actual
  service with a sync-only echo fixture on the same manager and response path.
  All five real process descriptions are selected; raster execution smoke tests
  run separately. The [current proposal](../validation/cite-teamengine/current/README.md)
  records 36 passes, 5 failures and 13 skips. It is not certification; historical
  predecessor results remain separate.

## Recorded checks

These are dated observations, not permanently current test counts or guarantees:

- pygeoapi boundary cleanup, **2026-10-25**: **562 tests passed**; final
  `make validate` coverage **95.97%** (`make test`: **96.07%**, with the existing
  HTTPS deadline-timer branch varying by timing). Both commands pass. Geonovum
  still matches eight reviewed findings; CITE remains **36 passed / 5 failed /
  13 skipped**, with every case status unchanged. Its discovery, conformance and
  OpenAPI capture exactly matches the pre-refactor run. Release smoke checks
  cover all five operations and result downloads. New regressions verify native
  subscriber-capability handling, global-state/API-instance isolation and
  preserved typed exception contracts; reviewed baselines are unchanged.

- Independent execution review, **2026-10-25**: **548 tests passed**, **96.07%
  coverage**. `make validate` (including `make test`) passes; Geonovum matches
  all eight reviewed findings. CITE remains **36 passed / 5 failed / 13 skipped**,
  with identical individual case statuses and no baseline changes. Local TLS
  regressions reuse generated TIFF references and reject private DNS for the
  service's own hostname. Fresh-process checks verify canonical HTTPS result
  links with proxy and native route prefixes. The release passes all five
  sample-raster operations and downloadable results. Public HTTPS, proxy routing
  and worker capacity still require deployment-specific verification.

- Demo stabilization, **2026-10-25**: **536 tests passed**, **95.85% coverage**
  (integrated validation checkpoint: 528 tests). `make test` and `make validate`
  pass; Geonovum still matches the eight reviewed findings. CITE remains strict
  and reports the same **36 passes, 5 failures and 13 skips**, with identical
  individual case statuses. Reviewed baselines are unchanged. The release
  passes all five operation smoke checks with the packaged AHN4 raster,
  TIFF/GeoJSON downloads, README commands and the point-sampling example.
  Saved downloads survive a normal release stop/start. Swagger and ReDoc render
  the live catalogue without JavaScript errors or empty Swagger tag sections.
  Read-only sample discovery no longer claims CRUD/CQL2; all 26 OpenAPI paths
  remain, with only the two unsupported CQL query POSTs removed.

- Async readiness/OpenAPI review, **2026-10-25**: **519 tests passed**,
  **95.72% coverage**. Swagger renders the retained operation groups without
  unused generic tags in headless Chromium; all 26 OpenAPI paths and their
  operation groupings match the pre-change definition. Quality/pre-commit,
  public/integration configuration/OpenAPI and release smoke/isolation checks
  pass. The reviewed eight-finding checker baseline is unchanged. PostgreSQL
  execution was reviewed in source, not implemented or integration-tested;
  see [the readiness review](async-readiness.md).

- Public samples, **2026-10-25**: **517 tests passed**, **95.71% coverage**.
  Native Features collection/item/paging responses validate against the official
  offline schemas. The raster download matches the supplied file's checksum;
  points sample valid pixels and the polygon contains the points inside the
  raster footprint. Quality/pre-commit, configuration/OpenAPI and release
  isolation checks pass. The packaged release serves all three datasets and
  accepts its point Features response directly for sampling. The reviewed
  eight-finding Processes checker baseline is unchanged.

- Landing and API documentation, **2026-10-25**: **509 tests passed**, **95.49% coverage**.
  ReDoc renders the live API catalogue in headless Chromium using pinned 2.5.3;
  the moving `latest` bundle reproduces a classic-script syntax error. ReDoc
  and Swagger HTML requests emit no false locale warnings, including on a cold
  template cache. JSON-LD landing requests selected by query or Accept preserve
  upstream response bytes and expose HTTP links without a server exception.
  Quality, configuration/OpenAPI, release execution and
  isolation checks pass. External CDN access remains required for the renderer.

- Raster operations, **2026-10-24**: **493 tests passed**, **95.39% coverage**.
  Sampling, classification and polygonization cover HTTPS/inline inputs, band
  selection, CRS handling, Point/MultiPoint/FeatureCollection sampling, all four
  TIFF/GeoJSON delivery modes, downloads,
  limits and errors. Quality/pre-commit, configuration/OpenAPI and release
  isolation checks pass. Host and separate client-container smoke checks pass;
  stored TIFF and GeoJSON downloads survive restart. The eight-finding Geonovum baseline
  adds only one conditional async expectation per new process. External client
  GeoJSON UI behavior remains untested.
  Logging regressions retain upstream descriptions/translation and normal
  diagnostics; release startup/discovery/execution logs contain neither the
  false metadata locale warnings nor the unused AsyncAPI file warning.

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
are summarized in [history](history.md); their full records remain in Git history.

[processes-core]: https://docs.ogc.org/is/18-062r2/18-062r2.html
[abstract-tests]: https://docs.ogc.org/is/18-062r2/18-062r2.html#_abstract_test_suite
[official-schemas]: https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi/schemas/
[process-example]: https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/ProcessDescription.json
[execute-example]: https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/Execute.json
