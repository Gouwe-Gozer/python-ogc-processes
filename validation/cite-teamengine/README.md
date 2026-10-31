# OGC CITE / TEAM Engine

`make validate-cite` runs the official OGC API – Processes 1.0 ETS against an
isolated instance of **Raster Processes API**. It uses the same application,
pygeoapi 0.24.0, durable PostgreSQL manager, separate worker, processors and result
handling as the normal deployment, plus one test-only echo process. Shared service
wiring is extended from `compose.base.yml`; there is no parallel API implementation.

## Prerequisites and one-command execution

Install Docker with Compose 2.24+, GNU Make, user-installed
`uv` and Python 3.12. Then run from the repository root:

```bash
uv sync --locked --all-groups
make validate-cite
```

No host Java, Maven or TEAM Engine installation is needed. Docker pulls the
official image in [`runner.json`](runner.json), pinned by digest: suite **1.3**,
TEAM Engine **6.0.0-RC2**. The engine version is the one shipped by OGC's latest
published Processes-suite image, not a claim about the latest standalone engine.
Image/registry access and external schema downloads require network connectivity.
The published suite image is for Linux/amd64; other architectures need Docker emulation.

The runner:

1. Creates a unique `raster-cite-*` Compose project and effective config copied
   from the canonical public config. It adds only internal network paths and
   the `cite-echo` fixture.
2. Builds/starts the real API, PostgreSQL and worker, using fresh named volumes
   and a randomly allocated loopback-only API port.
3. Runs independent synchronous raster checks and async info/warp/status/results/
   download checks before invoking the official suite.
4. Invokes the official suite's supported `TestNGController` Java CLI from the
   unmodified image, using the engine libraries already installed there.
5. Requests the engine's official HTML report/ZIP alongside native TestNG XML
   and EARL; collects JSON/HTML/Markdown summaries, versions,
   image identities, application commit/dirty state, configuration and logs.
6. Removes its own temporary containers, network, result/database volumes and application
   image tag, retaining the reports. It never stops the ordinary API or other projects.

The echo fixture has matching input/output identifiers required by the suite,
uses the ordinary processor/formatter interfaces, and the durable manager
advertises both execution modes. Async requests run through the actual worker.
The echo returns Python values so the HTTP boundary serializes JSON once.
It accepts a required string plus optional integer array (up to 16 items),
4/6-coordinate bounding box, mixed string/integer/qualified-object value and
`pause` (0–5 seconds). Omitted values have defaults; pause is not an output.
Strings are limited to 4,096 characters and integers to ±1,000,000. Bounding boxes
are echoed structurally, without interpreting their coordinates.

Matching outputs support value transmission: a single raw JSON value, a result
document, or `multipart/related` for multiple raw outputs. This MIME formatter is
validation-only. HTTP/PostgreSQL regressions check values, schemas, output selection,
invalid inputs and sync/async parity; CITE exercises the real worker and pending
result retrieval. Public raster contracts and production processes are unchanged.

The pinned suite flattens array item types into input types and can consequently
send a scalar for a string-array input. The fixture uses integer arrays with strict
validation instead. Its mixed application-object choice precedes bbox because the
suite's generic object generator otherwise supplies a qualified string to bbox.
Neither accommodation accepts values outside the advertised schemas.
The runner requests all-process testing, but the pinned suite's process-description
class inherits `testAllProcesses=false` without assigning the supplied setting.
Those methods therefore inspect the echo, not every raster description. Our
HTTP/schema tests cover the raster descriptions; separate raster smoke tests
exercise actual operations. Method names alone do not establish that every
transport or transmission mode was tested.

## Reports and exit behavior

Reports are in `runtime-data/cite/raster-cite-<unique-id>/`. Open the **official
TEAM Engine report** at `reports/testng/<run-id>/result/index.html`, or share
`official-report.zip` in the run's root directory. Keep the complete
`result/` directory together when copying the unpacked report.

The pinned engine's original `reports/testng/<run-id>/result.zip` is retained
unchanged. Its ZIP writer flattens asset directories, so our runner also packages
the unchanged official HTML/assets as `official-report.zip`, preserving their
relative paths. The report itself is generated entirely by TEAM Engine. Some
test-source/Javadoc links target its web application and are unavailable offline;
test results, request/response details and presentation assets remain local.

Our lightweight `summary.html` and `summary.md` link to those official reports;
they remain separate from TEAM Engine's presentation. `summary.json` indexes
individual cases and `metadata.json` records versions and report paths. Native
XML/EARL remain under `reports/testng/<run-id>/`. CLI/application/startup/cleanup
logs and the exact effective config are retained beside them. GitHub Actions
uploads the complete run directory, including the official HTML and ZIP.

The Python runner returns **0** for a complete run without failures, **1** for
reported test failures and **2** for infrastructure/report/cleanup errors.
GNU Make wraps unsuccessful recipes in its own nonzero status; read the
`FAIL` versus `INFRASTRUCTURE ERROR` output and retained logs to distinguish them.
Missing reports (including official HTML/ZIP) or malformed/inconsistent totals
never count as a pass.

The [combined-deployment observation](combined/README.md) records **45 passed,
4 failed, 5 skipped**, with explicit classifications. The expanded echo result
below is a subsequent observation; historical snapshots are unchanged.
Reported failures still make `make validate-cite` fail; CITE is not a mandatory
PR gate. The earlier
[synchronous observation](current/README.md) (**36/5/13**) and
[predecessor snapshot](baseline/README.md) remain historical, unchanged records.

## Expanded echo coverage (2026-10-31)

Run `raster-cite-968ddd0eac91`: **49 passed / 5 failed / 0 skipped**, compared with
the historical combined **45 / 4 / 5**. All 54 official verdicts remain unmodified;
the command still exits nonzero. All five former skips now pass: array input,
bounding-box input, mixed input/output descriptions, and not-ready results.
The same fixture passes HTTP/PostgreSQL regression tests for sync/async results.

| Remaining method(s) | Assessment and follow-up |
| --- | --- |
| `testJobCreationInputRef`, `testJobCreationInputValidation` | The suite now takes its multipart branch and cannot find `teststring`, although independently decoded JSON parts contain it. Its `validateMultipartResponse` calls Java MIME `getContent().toString()` rather than decoding JSON bytes. Assessed checker limitation; retain correct JSON part types and failed verdicts. The initial-valid-response check still prevents the intended invalid-input check. |
| `testJobResultsAsyncRawValueOne` | Newly fails as a suite polling limitation. The retained report contains a successful job completed about 10 seconds after submission, but says “20 seconds.” `loopOverStatus` uses an instance-wide `attempts` counter without resetting it between tests and checks the counter before examining the successful status. The pause test adds real queue pressure. Keep actual async parity/pending-result regressions; do not shorten the requested pause or manufacture immediate completion. |
| `testJobList`, `testJobListSuccess` | Unchanged optional Job List expectations; unsupported/unadvertised, returning 405. |

These classifications follow the pinned [Jobs implementation][echo-jobs-source].
The mixed-schema checks examine only the echo because of the unassigned
`testAllProcesses` field in [CommonFixture][echo-common-source] and its use in
[OGCProcessDescription][echo-description-source]. An exploratory run with
`testallprocesses=off` produced the same verdicts; no new scope option is retained.

Coverage limits remain explicit: the echo has no binary input or reference
outputs. Several passing method names therefore do not prove binary, referenced-input
or reference-transmission coverage; inspect their requests. Raster smoke tests
and our HTTP/security tests supply separate evidence. The earlier string/binary
`oneOf` schema overlap is unchanged: the two affected methods now follow the
legitimate multipart path because the fixture has multiple outputs, rather than
reaching that bundled response-schema check.

The complete official report is retained under
`runtime-data/cite/raster-cite-968ddd0eac91/`; no reviewed baseline was replaced.
Geonovum independently still matches the **one-diagnostic** combined baseline.

[echo-jobs-source]: https://github.com/opengeospatial/ets-ogcapi-processes10/blob/7ec421d9fc23718953c7ab973d3f6cc23b33e76e/src/main/java/org/opengis/cite/ogcapiprocesses10/jobs/Jobs.java
[echo-common-source]: https://github.com/opengeospatial/ets-ogcapi-processes10/blob/7ec421d9fc23718953c7ab973d3f6cc23b33e76e/src/main/java/org/opengis/cite/ogcapiprocesses10/CommonFixture.java
[echo-description-source]: https://github.com/opengeospatial/ets-ogcapi-processes10/blob/7ec421d9fc23718953c7ab973d3f6cc23b33e76e/src/main/java/org/opengis/cite/ogcapiprocesses10/ogcprocessdescription/OGCProcessDescription.java

## Job List observation (2026-10-31)

Run `raster-cite-71c76ab441cd`: **52 passed / 2 failed / 0 skipped**.
`testJobList` and `testJobListSuccess` now pass against the real durable manager.
The two remaining failures are `testJobCreationInputRef` and
`testJobCreationInputValidation`, with the JSON MIME-content issue described above.
`testJobResultsAsyncRawValueOne` passes this run; its timing-sensitive polling
failure is not treated as an application fix or a guarantee for later runs.
The polling method checks its attempt limit before examining a fetched terminal
status; earlier claims about counter carry-over and pause-test queue pressure were
not established by the retained evidence.

The unchanged official report and verdicts are under
`runtime-data/cite/raster-cite-71c76ab441cd/`. Historical snapshots remain unchanged.
New PostgreSQL/HTTP tests additionally cover all required Job List filters,
empty lists, pagination, safe metadata, configured public links and error headers.
A real API/database restart test confirms queued and completed listings survive.

## Supported CLI, REST and browser fallback

Both the official Java CLI and the authenticated REST interface were exercised.
CLI is used by default because it writes native files directly, needs no Tomcat
startup/login, and avoids ZIP extraction or browser automation. The engine's
`acceptMediaType=application/zip` test-run property requests its own HTML/ZIP
generation without rerunning tests or replacing the XML/EARL. The pinned
[official executor](https://github.com/opengeospatial/teamengine/blob/6.0.0-RC2/teamengine-spi/src/main/java/com/occamlab/te/spi/executors/testng/TestNGExecutor.java)
uses the same report generator as REST's `Accept: application/zip`. The official
[TEAM Engine guide](https://opengeospatial.github.io/teamengine/users.html)
documents CLI, REST and browser operation; the suite's controller documents its
[programmatic entry point](https://github.com/opengeospatial/ets-ogcapi-processes10/blob/1.3/src/main/java/org/opengis/cite/ogcapiprocesses10/TestNGController.java).

For manual diagnosis:

```bash
make validate-cite CITE_ARGS=--browser
```

This explicitly leaves the isolated API/database/worker and TEAM Engine web
instance running. It does not alter an existing deployment. The
command prints a randomly allocated loopback-only URL and exact cleanup commands;
these are also in its `metadata.json`. Wait for Tomcat startup if the page is
initially unavailable. Log in with the image's local test account **ogctest / ogctest**.
Create a session for Processes 1.0, set the landing page to `http://api:8080`,
echo ID to `cite-echo`, select **Test all processes**, and start the run.
Use the printed cleanup commands when finished. Browser mode itself claims no test result.

The authenticated REST listing is `/teamengine/rest/suites`; the installed
controller is `/teamengine/rest/suites/ogcapi-processes-1.0/run`. It accepts
`iut`, `echoprocessid`, `testallprocesses=on` and `processtestlimit=0`, with Basic
authentication and `Accept: application/xml` for direct XML results.
Use the image's advertised endpoints; version path conventions differ between engine versions.

## Baseline policy and CI

The runner writes only ignored run directories, never reviewed evidence. Compare
new reports method by method, review applicability and requirements, and propose
baseline updates explicitly as tracked file changes. Include native XML/EARL,
metadata/configuration, a result summary and a classification/action for every failure.
A matching pass count alone is insufficient. Do not alter production behavior,
filter test failures, advertise unsupported capabilities or enable another job
manager to improve the score.

The **OGC CITE validation** GitHub Actions workflow is manually triggered only.
It preserves complete run reports as artifacts even when tests fail. It is
independent of normal PR checks; local execution does not need GitHub or secrets.
