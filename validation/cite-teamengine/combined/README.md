# Combined-deployment CITE observation

Official Processes ETS **1.3** / TEAM Engine **6.0.0-RC2**, using the digest in
[`../runner.json`](../runner.json), against the default API/PostgreSQL/separate-worker
deployment. Source/configuration/image fingerprints and dirty-working-tree status
are in `metadata.json`; this is development evidence, not a clean release or
certification. Original run: `raster-cite-803b148e26c3`.

**45 passed / 4 failed / 5 skipped**, compared with the historical synchronous
profile's **36 / 5 / 13** in [`../current/`](../current/README.md).
All 54 methods remain accounted for. The official verdicts are unmodified.

## Remaining failures

| Method | Assessment |
| --- | --- |
| `testJobCreationInputRef` | Same bundled-schema `oneOf` string/base64 ambiguity as the historical run; the captured request is not proof of actual input-reference coverage. |
| `testJobCreationInputValidation` | Same schema ambiguity interrupts the initial valid response before the intended invalid-input check. Keep actual input-validation regression tests. |
| `testJobList` | The suite attempts the optional Job List operation, which is deliberately not supported or advertised; the default service returns 405. |
| `testJobListSuccess` | The same optional Job List expectation: its 405 exception is not a job-list document. Do not add listing merely to satisfy this test. |

The earlier synchronous-status assumptions no longer fail when the suite sees
the async-capable echo. Additional async methods now execute. Pending job status
documents expose a standard `monitor` link; successful status documents link to
results. This helps clients poll through links and allows the suite's result
traversal to work. These links are an interoperability improvement, not a claim
that their earlier absence violated Core's required status schema.

## Skips and evidence boundary

Two tests skip because the echo lacks array/bbox inputs, two because it lacks
mixed-type input/output schemas, and the pending-results test because it has no
`pause` input. Separate HTTP/container tests verify actual pending-result 404s,
interruption, deadlines and restart persistence.

All five raster process descriptions are selected. The executable suite uses
the test-only echo through the real durable manager and worker; separate raster
smokes execute actual sync/async information and warp, including GeoTIFF downloads,
and all five processes are covered by container tests. The official suite still
uses bundled response schemas for several checks; it does not replace validation
of our generated OpenAPI.

Native XML/EARL, every method's status, discovery/configuration, version/image
metadata and smoke logs are retained here. The original run and each fresh
`make validate-cite` run retain the official HTML and shareable ZIP under
`runtime-data/cite/`; CI uploads the full run directory. Historical synchronous
and predecessor snapshots remain unchanged.

The command remains strict: these four failures return a nonzero result. There
is no pass allowlist and these numbers are observations, not mandatory targets.

Official references: [suite 1.3](https://github.com/opengeospatial/ets-ogcapi-processes10/tree/1.3),
[execution/result checks](https://github.com/opengeospatial/ets-ogcapi-processes10/blob/1.3/src/main/java/org/opengis/cite/ogcapiprocesses10/jobs/Jobs.java),
and [Core 1.0](https://docs.ogc.org/is/18-062r2/18-062r2.html).
