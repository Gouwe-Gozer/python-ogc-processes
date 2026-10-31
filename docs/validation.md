# Validation and standards

The normative reference is [OGC API – Processes Part 1: Core 1.0.0][processes-core]
(18-062r2), including [Annex A][abstract-tests]. Use the official [schemas][official-schemas]
for validation. [ProcessDescription.json][process-example] and [Execute.json][execute-example]
illustrate representations; they are not schemas. Tests use an unchanged,
checksummed [offline snapshot](../tests/schemas/ogc-processes-1.0/README.md).

## Conformance claims and gaps

The default durable deployment advertises Processes Core, JSON, OpenAPI 3.0,
OGC Process Description and Job List, plus inherited Common/read-only Features
classes. It implements sync execution, durable async submission/status/results
and filtered/paginated job listing. Synchronous calls deliberately create no
retained job (Permission 7). Callback and Dismiss are not advertised.

Conformance corrections are scoped to the API instance: Callback follows the
manager's `supports_subscribing`, independently of `is_async`; Job List follows
`supports_job_list`. Manager construction does not change upstream global claims.
Read-only GeoJSON sample providers omit unsupported CRUD/CQL2 claims and query
POSTs. CQL requests fail clearly instead of returning unfiltered data; native
bbox, paging and individual-feature reads remain available.

The explicit synchronous opt-out retains no jobs or Job List claim. pygeoapi
still registers its native `/jobs` route, returning an empty list, although that
route is outside the synchronous OpenAPI contract. `respond-async` is ignored
without an applied preference or job Location. Unknown job resources return the
standard `no-such-job` exception; durable pending results use `result-not-ready`.

Passing regressions or matching reviewed diagnostics is **not certification**.
Current external evidence has these limits:

| Assessment | Recorded observation | Interpretation |
| --- | --- | --- |
| Geonovum 1.3.2 | One reviewed diagnostic in the default Job List deployment | `maxDuration` serialization check conflicts with Requirement 74; see [evidence and baseline](../validation/geonovum/README.md). |
| CITE Processes ETS 1.3 / TEAM Engine 6.0.0-RC2 | 52 passed / 2 failed / 0 skipped, 2026-10-31 | Both remaining methods stop at JSON MIME-content checks; raw failures and response evidence remain [public](../validation/cite-teamengine/current/README.md). |

These are dated observations tied to recorded versions/source state, not promised
test counts for every revision. The CITE snapshot records a dirty development
tree. Its async raw-value polling test passed that run, but a timing-sensitive
suite failure has also occurred. Keep failures visible and inspect new reports
method by method. Do not rewrite a baseline to obtain a green check.

## Repeatable commands

Use Python 3.12, user-installed uv, GNU Make and Docker Compose 2.24+;
run `uv sync --locked --all-groups` first. Registry/package/schema access is
needed for uncached external tools; no host Node, Java or Maven is required.

| Command | Checks and scope |
| --- | --- |
| `make test` | Ruff, Bandit, pytest/coverage and configuration/OpenAPI checks; reports under `runtime-data/validation/`. PostgreSQL/container tests are opt-in as described in [async verification](asynchronous-execution.md#scope-and-verification). |
| `make validate-geonovum` | Isolated API/PostgreSQL/worker stack, sync/async raster smokes and exact reviewed-baseline comparison; reports under `runtime-data/geonovum/`. Explicit `GEONOVUM_INPUT` targets an existing API. |
| `make validate` | `make test` plus Geonovum; excludes CITE. |
| `make validate-cite` | Official pinned executable suite against an isolated combined stack with validation-only echo; reports under `runtime-data/cite/`. |

The isolated runners remove only their own containers, networks, volumes and
application image tags; existing deployments are untouched. Geonovum returns
success for an exact reviewed-baseline match, not a clean compliance report.
CITE remains strict: recorded failures make the command fail. Python runners
distinguish findings (1) from infrastructure errors (2); Make wraps failures in
its own nonzero status. Neither workflow updates baselines automatically.

PR checks cover routine tests, release/runtime checks and Geonovum. CITE is a
separate manually triggered CI workflow; reports are uploaded even on failure.
For detailed tool options and review policy, use the [Geonovum](../validation/geonovum/README.md)
and [CITE](../validation/cite-teamengine/README.md) READMEs.

Fresh CITE runs include native XML/EARL, summaries, metadata/configuration/logs,
and TEAM Engine's official HTML report at
`runtime-data/cite/raster-cite-<id>/reports/testng/<run-id>/result/index.html`.
Share `official-report.zip` to retain all relative assets. Generated run directories
are ignored; they are not files a fresh clone is expected to contain. The
[checked-in snapshot](../validation/cite-teamengine/current/README.md) preserves
the latest reviewed observation and limitations, not a mandatory score.

## OGC review guide

| Area | Normative pointer | Public implementation/evidence |
| --- | --- | --- |
| Landing, conformance and API definition | Sections 7.4–7.8 | Native discovery plus scoped corrections; HTTP/official-schema and OpenAPI tests |
| Process discovery and descriptions | Sections 7.9–7.10; Requirements 49–51 | Explicit process contracts; [value/wire distinction](inputs.md#ogc-scope-and-deployment) |
| Input delivery and validation | Requirements 18, 20, 22, 24 | Shared bounded HTTPS resolution, inline base64/qualified objects and actual raster decoding |
| Execution preferences and defaults | Requirements 25–27, 34 | Sync default, async 201/Location, acceptance/status tests and explicit sync opt-out |
| Output delivery | Requirements 28–32 | [Native, document and reference forms](results.md#http-contract); production processes have one output each |
| Job resources and errors | Requirements 35–46; Permission 7 | Durable status/results, not-ready/unknown/failed jobs, restart/interruption tests; no retained sync jobs |
| Job List | Section 11, Requirements 64–79 | Bound SQL filters, pagination, processID, official schema and restart coverage |
| Exceptions and OpenAPI | Requirement 15; Section 10 | [Catalogue](errors.md), generated definition and actual error/schema tests |

Reassess conditional requirements when adding repeated inputs, new types, multiple
outputs or execution capabilities. The validation echo offers arrays, bbox,
mixed types and multipart output specifically to exercise shared infrastructure;
the five production processes need not expose those process-specific capabilities.
No automatic multipart formatter is supplied for arbitrary custom processes.

Keep metadata, runtime validation, generated OpenAPI and executable examples
consistent. Check pixels/CRS/transforms/nodata and allocation limits for raster
changes, as well as HTTP status, headers and representations. Test reference
acquisition and result delivery independently. Use [adding a process](adding-a-process.md)
and the [development checks](development.md).

## Published binary-schema limitation

The unchanged official `inputValueNoObject.yaml` uses `oneOf` with an unrestricted
string and a byte-formatted string. Base64 matches both, so strict validation can
reject valid inline binary values. The official examples use the base64/encoding/
mediaType representation implemented here. Tests retain this overlap explicitly.

Discovery, reference requests/results and exceptions validate against the official
snapshot. Inline binary documents additionally use application schemas and actual
TIFF decoding. Official fixtures are not modified to hide overlap; these checks
do not establish complete conformance. The current two CITE failures concern a
different, multipart JSON-decoding check; see the [CITE assessment](../validation/cite-teamengine/current/README.md).

## Test and checker coverage

- Raster/HTTP tests check all five contracts, basic output correctness, metadata,
  four file-delivery modes, errors and independent downloads.
- Local HTTP/TLS origins exercise HTTPS pinning, redirects, deadlines, limits and
  cleanup without mutable public raster downloads. Official schemas are offline.
- Storage/startup tests cover quotas, expiry, safe paths, locking, atomic publication
  and configuration errors. Container tests cover real workers, persistence,
  interruption/restarts and the independent custom-process installation.
- CITE uses the validation echo through the actual durable manager/worker. Despite
  the runner's all-process setting, the pinned suite's description class leaves
  `testAllProcesses=false`; description checks therefore inspect echo. Separate
  raster tests/smokes supply the production evidence. Echo has no binary input or
  reference output, so passing names do not prove those transports were tested.
- The local-file example has HTTP coverage; it does not verify external browser
  client controls or map rendering.

## Client interoperability

Service schema validation and useful client controls are separate concerns.
Earlier testing observed a binary GeoTIFF input rendered as plain text, without
file/URL controls, and map drawing interfering with pasted GeoJSON. The client
name/build and exact exchanges were not captured; these are unverified client
interoperability/UX observations, not established OGC compliance violations.

The service advertises binary values using the official Process Description
conventions and accepts HTTPS/inline base64. Sampling now accepts Point,
MultiPoint and point FeatureCollections. The earlier demo/`anyOf` alternative
and FeatureCollection-only sampling restriction are removed and have regressions.

For a repeatable client check, record client/service versions and exact exchanges
using [public samples](sample-data.md) and [operation requests](raster-operations.md).
Verify file/URL entry, qualified GeoJSON input, async polling, native outputs,
document/reference results, HTTP 204/Link downloads, expiry and [error details](errors.md).
GeoTIFF map rendering is a client capability; downloading/processing rasters does
not require the API to provide WPS or a tile service.

[processes-core]: https://docs.ogc.org/is/18-062r2/18-062r2.html
[abstract-tests]: https://docs.ogc.org/is/18-062r2/18-062r2.html#_abstract_test_suite
[official-schemas]: https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi/schemas/
[process-example]: https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/ProcessDescription.json
[execute-example]: https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/Execute.json
