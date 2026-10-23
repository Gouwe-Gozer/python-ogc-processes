> Historical predecessor results. These do not validate Terrio Processes;
> the inputs, image and commit below identify the original service.

# CITE/TEAM Engine baseline — 2026-08-24

This directory records the latest OGC API - Processes 1.0 CITE run against
the integration configuration. The run uses a controlled echo process to test
the OGC API and temporary job-manager behaviour. It is useful validation
evidence, but it is not a conformance claim for the terrain process.

## Run metadata

- API source commit: `aaa97cb966123e3f548216b933f1494a55ed1c51`
- Suite: `ogcapi-processes-1.0-1.3`
- TEAM Engine image: `ogccite/ets-ogcapi-processes10`
- Image digest: `sha256:8879e2d608e654d1f68aa94a2fd3b9bb1376f400737a2732ed32915a8e5211e8`
- Landing page: `http://api:8080/`
- Echo process: `async-echo`
- Test all processes: selected
- Process-description limit: `3` (ignored because all exposed processes were selected)
- Execution time: `2026-08-24T06:50:54Z` to `2026-08-24T06:51:00Z`

## Results

| Test group | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Core | 40 | 3 | 2 |
| OGC Process Description | 5 | 0 | 2 |
| Job List | 2 | 0 | 0 |
| **Total** | **47** | **3** | **4** |

Compared with the 2026-08-14 run, one failure became a pass:
`testJobCreationSuccessAsync` no longer rejected the returned job-status
document. The total therefore changed from 46 passes and 4 failures to 47
passes and 3 failures. This run alone does not establish why that result
changed.

## Scope of the evidence

The integration configuration exposes only `async-echo`, backed by pygeoapi's
temporary TinyDB job manager. Consequently, all execution, process-description
and job-management results in this run concern that controlled fixture and the
shared pygeoapi routes. The setting to test all processes therefore still tests
only `async-echo`.

The run does not discover or execute `bgt-land-cover-summary`. It does not prove
asynchronous execution, persistent jobs, restart recovery or CITE conformance
for the terrain process. Behaviour of the terrain process is covered by its own
unit, integration and live-data checks.

## Remaining findings

1. `testJobCreationInputRef` and `testJobCreationInputValidation` both receive
   `{"id":"message","value":"teststring"}`. CITE reports that this body
   matches more than one `oneOf` alternative and therefore rejects it as
   ambiguous. The runtime response and generated response schemas need to be
   reviewed together before deciding whether the response or the documented
   alternatives should change.
2. `testJobResultsExceptionResultsNotReady` requests results while an echo job
   is still running, but receives no exception document of type
   `result-not-ready`. The tested OGC API - Processes 1.0 requirement expects
   that exception.

The four skipped tests are conditional. Two cover array and bounding-box input
forms not offered by the echo fixture; two cover mixed-type process inputs and
outputs not offered by the fixture.

## Evidence

- `testng-results.xml` contains the complete per-test result and failure data.
- `earl-results.rdf` contains the machine-readable EARL assertions.
- `teamengine-log.xml` contains the submitted run settings and concise failure
  messages.
