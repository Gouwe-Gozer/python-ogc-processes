# OGC CITE / TEAM Engine

`make validate-cite` runs the official Processes 1.0 ETS against an isolated
Python OGC Processes/PostgreSQL/worker stack. It uses the real application,
processors and result handling plus a validation-only echo. Shared wiring comes
from `compose.base.yml`; there is no parallel API implementation.

## Run

Install Docker with Compose 2.24+, GNU Make, user-installed uv and Python 3.12.
From the repository root:

```bash
uv sync --locked --all-groups
make validate-cite
```

No host Java, Maven or TEAM Engine installation is needed. [runner.json](runner.json)
pins the official image by digest: Processes ETS **1.3**, TEAM Engine
**6.0.0-RC2**, suite source commit `7ec421d9fc23718953c7ab973d3f6cc23b33e76e`.
These are the workflow's versions, not claims about the latest upstream releases.
Registry/schema downloads need network access. The suite image is Linux/amd64;
other architectures require Docker emulation.

The Python runner:

1. Creates a unique `raster-cite-*` project from the canonical configuration,
   changing internal URL/data paths and registering `cite-echo`.
2. Builds/starts API, PostgreSQL and worker with fresh volumes and a random
   loopback-only API port.
3. Checks the five raster operations and sync/async info/warp/status/results/downloads.
4. Invokes the unmodified image's supported `TestNGController` Java CLI.
5. Collects official HTML/ZIP, TestNG XML/EARL, summaries, exact configuration,
   versions, image/source fingerprints, dirty-tree status and logs.
6. Removes only its own containers/network/volumes/application image tag, retaining
   reports. It does not stop an ordinary deployment or another Docker project.

## Coverage and limitations

Echo is a direct processor using the same execution/formatter interfaces and
durable worker as production. Matching input/output IDs satisfy the suite's
echo contract. It offers a bounded string, integer array, 4/6-coordinate bbox,
mixed value and bounded pause; output selection supports raw JSON, output-keyed
documents and `multipart/related` for multiple raw outputs. The MIME formatter
is fixture-specific, not an automatic formatter for arbitrary processors.

Fixture choices accommodate two pinned-suite generation limitations: integer
arrays avoid its scalar string-array generation, and the mixed application-object
choice precedes bbox to avoid a generated qualified string being treated as bbox.
The fixture still rejects values outside its advertised schemas; no production
raster contract is changed for the validator.

The runner requests all-process testing, but the suite's description class does
not assign that setting and inspects echo only. Echo has no binary input or
reference output; passing method names do not prove those delivery modes were
tested. HTTP/schema/security regressions and raster/container smokes cover them
separately. See [CommonFixture](https://github.com/opengeospatial/ets-ogcapi-processes10/blob/7ec421d9fc23718953c7ab973d3f6cc23b33e76e/src/main/java/org/opengis/cite/ogcapiprocesses10/CommonFixture.java)
and [OGCProcessDescription](https://github.com/opengeospatial/ets-ogcapi-processes10/blob/7ec421d9fc23718953c7ab973d3f6cc23b33e76e/src/main/java/org/opengis/cite/ogcapiprocesses10/ogcprocessdescription/OGCProcessDescription.java).

The [reviewed public snapshot](current/README.md) records **52 passed / 2 failed /
0 skipped**, including passing Job List tests. The two failures stop at a MIME
JSON-content check; native reports retain responses containing the expected value.
Async raw-value polling has also shown timing-sensitive suite failure. These
assessments, scope limits and supporting reports stay public. No failed verdict
is changed to pass or skip. See the broader [validation guide](../../docs/validation.md)
for the separate official binary-schema overlap and current service claims.

## Reports and exit behavior

Fresh reports are in `runtime-data/cite/raster-cite-<id>/`. Open the official
report at `reports/testng/<run-id>/result/index.html` or share `official-report.zip`.
Keep all relative HTML/assets together. The engine's original `result.zip` is
also retained; its ZIP writer flattens asset directories, so the runner packages
the unchanged official HTML/assets again with their directory structure intact.
Some test-source/Javadoc links need the engine web application and will not work
offline; result details and presentation assets remain local.

`summary.html`/`summary.md` link to official reports; `summary.json` indexes every
case. `metadata.json` records versions, report paths and source identity. Native
XML/EARL, exact config/test parameters and application/CLI/cleanup logs remain
alongside them. CI uploads the complete run directory even after failures.

The runner returns **0** for complete runs without failures, **1** for test
failures and **2** for infrastructure/report/cleanup errors. Make wraps failures
in its own nonzero status; distinguish `FAIL` from `INFRASTRUCTURE ERROR` in logs.
Missing or inconsistent reports, including missing official HTML/ZIP, never pass.
Generated runs are ignored. The tracked `current/` snapshot is deliberately
reviewed evidence, not an automatically updated threshold.

## CLI, REST and browser diagnosis

The default Java CLI writes native files without starting Tomcat or authenticating.
Its `acceptMediaType=application/zip` requests the engine's official report
generation, using the same generator as REST's ZIP representation. Official
references: [TEAM Engine user guide](https://opengeospatial.github.io/teamengine/users.html),
[suite CLI controller](https://github.com/opengeospatial/ets-ogcapi-processes10/blob/1.3/src/main/java/org/opengis/cite/ogcapiprocesses10/TestNGController.java)
and [report executor](https://github.com/opengeospatial/teamengine/blob/6.0.0-RC2/teamengine-spi/src/main/java/com/occamlab/te/spi/executors/testng/TestNGExecutor.java).

For manual investigation:

```bash
make validate-cite CITE_ARGS=--browser
```

This leaves only the generated stack and engine web instance running and claims
no test result. Use the printed loopback URL and exact cleanup commands, also
recorded in `metadata.json`. Wait for Tomcat if initially unavailable. The image's
local test login is **ogctest / ogctest**. Create a Processes 1.0 session with
landing URL `http://api:8080`, echo ID `cite-echo` and **Test all processes**.
Apply the scope limitation above even when that setting is selected.

The authenticated REST listing is `/teamengine/rest/suites`; the pinned suite's
run endpoint is `/teamengine/rest/suites/ogcapi-processes-1.0/run`. Parameters are
`iut`, `echoprocessid`, `testallprocesses=on`, `processtestlimit=0`, with Basic auth
and `Accept: application/xml` for direct XML. Other engine versions may use
different paths; follow their advertised interface.

## Review policy and CI

The runner never rewrites tracked evidence. Compare methods, captured exchanges,
requirements and applicability before explicitly updating a snapshot. Preserve
native verdicts, metadata and classifications of every failure/skip; matching
totals alone are insufficient. Do not change correct service behavior, filter
failures or advertise unsupported capabilities to improve a score.

The **OGC CITE validation** GitHub workflow is manually triggered, independent of
normal PR checks. Local execution needs no GitHub account or secrets.
