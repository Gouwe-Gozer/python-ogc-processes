# Current-service CITE baseline proposal — 2026-10-25

This is a fresh observation for Raster Processes API, submitted for review with
this infrastructure change. It is not an acceptance threshold or certification.
The runner never writes this directory. The historical predecessor result in
[`../baseline/`](../baseline/README.md) is unchanged and is not an expected score.

## Tested implementation

- Suite: official OGC Processes 1.0 ETS **1.3**, source tag `1.3`, commit
  `7ec421d9fc23718953c7ab973d3f6cc23b33e76e`.
- Engine: **6.0.0-RC2**, the version bundled by OGC's current published Processes image.
- Image: `ogccite/ets-ogcapi-processes10:1.3-teamengine-6.0.0-RC2` pinned to
  `sha256:8879e2d608e654d1f68aa94a2fd3b9bb1376f400737a2732ed32915a8e5211e8`.
- Application base commit: `de8890c66b94cc106c8643b874d809677327ddd0`, plus the
  uncommitted validation branch. `metadata.json` records the dirty state, image
  identity and source/configuration checksums; this is not labelled a clean release.
- The canonical configuration retains all five real raster processes and
  `geo_processes.manager.OgcSynchronousManager`. Only the internal URL/sample
  paths and additional test-only `cite-echo` registration differ.
- Execution tests use the synchronous string echo, through the real Flask
  boundary, manager and result formatter. All process descriptions are selected
  (`testallprocesses=on`); the suite's process limit is disabled.
- A separate integration smoke run processes synthetic rasters through all five
  operations and downloads results. This is integration evidence, not a CITE test.

## Observed results

| Suite group | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Core | 30 | 4 | 11 |
| OGC Process Description | 5 | 0 | 2 |
| Job List | 1 | 1 | 0 |
| **Total** | **36** | **5** | **13** |

The native XML and EARL preserve all failures and skips. `summary.json` indexes
individual cases; the generated `summary.html`/`summary.md` in each local run
provide human-readable reports. `make validate-cite` exits unsuccessfully for
these failures. No allowlist converts them into passing tests.

## Individual failures

The suite uses some older requirement names; the clause numbers below refer to
[18-062r2](https://docs.ogc.org/is/18-062r2/18-062r2.html).

| Test | Requirement/class | Classification and evidence | Interoperability impact and action |
| --- | --- | --- | --- |
| `testJobCreationInputRef` | Core, Requirement 18; suite `/req/core/job-creation-input-ref` | Checker schema limitation and fixture coverage limitation. The native report shows a literal string request, not an input reference, and successful JSON string output rejected because multiple bundled response-schema alternatives match. | This failure does not establish a service reference defect or prove reference support. Keep the actual HTTPS raster/scalar integration tests; report the ambiguous bundled schema upstream. |
| `testJobCreationInputValidation` | Core, Requirement 24; suite `/req/core/job-creation-input-validation` | Checker schema limitation. It rejects the valid initial raw string response for the same `oneOf` overlap before reaching its invalid-input case. | No invalid-input rejection conclusion can be drawn from this method. Fixture tests verify controlled 400 responses; retain independent raster validation tests and report the schema issue upstream. |
| `testJobCreationOp` | Core, Requirements 16/26/28; suite `/req/core/job-creation-op` | Checker limitation for synchronous execution without retained jobs. In `Jobs.java`, its synchronous branch validates the raw HTTP 200 result with `getStatusValidator`, requiring `jobID/status/type`. | Ordinary synchronous clients receive the requested result. Do not manufacture a job-status body or persistent jobs: synchronous job creation is optional under Permission 7. Report the validator choice upstream. |
| `testJobCreationRequest` | Core, Requirements 17/26/28; suite `/req/core/job-creation-request` | Same synchronous status-document assumption as above, visible in the captured successful raw response and validator error. | Preserve normal raw/document behavior and review the suite's synchronous branch. This is not evidence that valid execution requests should return status documents. |
| `testJobList` | Optional Job List, `/req/job-list/job-list-op` | Outside the advertised profile; checker assumes a nonempty job list after execution. The native response is HTTP 200 with `jobs: []`. This service retains no jobs and does not advertise Job List. | No job-list capability is claimed. Do not introduce artificial records or enable another manager for this test. Reassess when job retention is implemented. |

No production API change was made for these findings. These classifications are
source/report-based assessments for review, not an external conformance ruling.

## Skips and coverage boundary

Nine methods skip because async is not advertised. Two skip for array/bbox
inputs absent from the echo fixture; two skip for mixed-type input/output
schemas absent from that fixture. They do not demonstrate coverage of every
input shape offered by the real raster processors.

Suite 1.3 forces `USE_LOCAL_SCHEMA=true` and uses its bundled OpenAPI example
for several response validators. It therefore does not replace validation of
our actual OpenAPI with pygeoapi and Geonovum. The original scalar/binary schema
overlap remains documented in the [validation guide](../../../docs/validation.md).

## Evidence and reproduction

Run `make validate-cite` from the repository root. Fresh evidence is placed in
`runtime-data/cite/raster-cite-<unique-id>/`, leaving this proposal untouched.

- `testng-results.xml` and `earl-results.rdf`: native, unmodified official outputs.
- `summary.json`: every method's group, status, requirement description and failure/skip reason.
- `metadata.json`: versions, image identities, application commit/dirty state and fingerprints.
- `api-config.yml` and `test-run-props.xml`: effective test configuration.
- `discovery.json`: actual conformance declarations, process catalogue and OpenAPI.
- `raster-smoke.log`: separate real-operation integration checks.

After committing/merging, rerun to obtain evidence identifying that exact clean
commit. Review native reports and classifications before explicitly replacing
baseline files; never copy a new run solely because its totals look similar.

Official sources: [suite 1.3](https://github.com/opengeospatial/ets-ogcapi-processes10/tree/1.3),
[Jobs.java](https://github.com/opengeospatial/ets-ogcapi-processes10/blob/1.3/src/main/java/org/opengis/cite/ogcapiprocesses10/jobs/Jobs.java),
[CLI controller](https://github.com/opengeospatial/ets-ogcapi-processes10/blob/1.3/src/main/java/org/opengis/cite/ogcapiprocesses10/TestNGController.java).
