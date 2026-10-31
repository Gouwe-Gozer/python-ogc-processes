# Reviewed CITE observation — 2026-10-31

Run `raster-cite-71c76ab441cd`: **52 passed / 2 failed / 0 skipped** against
the API/PostgreSQL/separate-worker deployment, including Job List. This is a
dated development observation, not certification or a required future score.
The [metadata](metadata.json) records application commit `da1e0779`, a dirty
working tree, source/configuration fingerprints and exact suite/image identities.
It predates subsequent architecture cleanups; run the [public workflow](../README.md)
for evidence against your own revision.

The official verdicts are preserved unchanged in [TestNG XML](testng-results.xml),
[EARL](earl-results.rdf) and the complete [TEAM Engine HTML/assets ZIP](official-report.zip).
Unzip the latter and open its `index.html`. [summary.json](summary.json)
indexes every case; [discovery.json](discovery.json), [api-config.yml](api-config.yml),
[test-run-props.xml](test-run-props.xml), [raster smoke](raster-smoke.log) and
[async smoke](async-smoke.log) retain the observed contract and test setup.
Original metadata paths describe the generated run directory, not this relocated
snapshot. No runner writes this directory automatically.

## Remaining failures and coverage limits

| Method | Assessment and evidence |
| --- | --- |
| `testJobCreationInputRef` | The valid request receives HTTP 200 `multipart/related`; the JSON string part contains `"teststring"`. The pinned MIME validator uses `getContent().toString()` on the Java content object instead of decoding the JSON bytes, so its substring test fails. Native XML retains the request, headers, body and failure. The captured request is not proof of referenced-input coverage. |
| `testJobCreationInputValidation` | Stops at the same valid multipart response before reaching its invalid-input check. Independent HTTP/input regressions cover controlled errors; this method does not establish invalid-input coverage. |

These are source/report-based assessments of a validator limitation, not an OGC
ruling. Keep the failed verdicts and correct JSON MIME types; no workaround or
allowlist converts these cases to passes. The relevant pinned code is
[`Jobs.validateMultipartResponse`](https://github.com/opengeospatial/ets-ogcapi-processes10/blob/7ec421d9fc23718953c7ab973d3f6cc23b33e76e/src/main/java/org/opengis/cite/ogcapiprocesses10/jobs/Jobs.java).

Both Job List methods pass. `testJobResultsAsyncRawValueOne` passes this run but
has shown timing-sensitive failure: its polling loop tests the attempt limit
before examining a fetched terminal status. Counter carry-over and pause-induced
queue pressure were not established; they are not retained as explanations.

Execution tests use validation-only echo through the real manager and worker.
The suite's process-description class does not apply the requested all-process
setting, so echo description coverage is not coverage of all five raster
descriptions. Echo has no binary input or reference output; separate HTTP/schema,
security and raster/container checks supply that evidence. See the public
[validation guide](../../../docs/validation.md).
