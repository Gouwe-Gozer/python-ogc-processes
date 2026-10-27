# Testing other OGC API – Processes services

[`scripts/validate_cite_external.py`](../scripts/validate_cite_external.py) is a
standalone runner for an existing OGC API – Processes Part 1 service. Copy the
single script to another project if useful: it needs Python **3.12+**, its
standard library and Docker, with no Raster Processes API installation, Java,
Maven, Compose or Python packages. It runs on Linux; the official Linux/amd64
image requires Docker emulation on other architectures.

It is separate from our application-specific `make validate-cite` workflow.
It does not deploy or modify the target API, install an echo process, run our
raster smoke tests or compare the target against our reviewed baselines.
The suite does submit executions and may create/dismiss jobs: use a service
and echo process intended for conformance testing.

## Run

```bash
python3 scripts/validate_cite_external.py \
  --base-url https://example.org/ogc-api \
  --echo-process echo
```

Use the API's landing-page URL, including any deployment prefix, without
`/processes` or query parameters. The URL and all advertised endpoint URLs must
be reachable **from the validator container**. The runner uses the official
Processes 1.0 ETS **1.3** / TEAM Engine **6.0.0-RC2** image, pinned by digest in
the script. Network access is required for image/schema downloads.

`--echo-process` must identify an existing echo operation compatible with the
suite. It builds requests from that process's advertised input/output schemas,
using sample values such as `teststring`, and expects corresponding outputs.
Matching input/output identifiers are the simplest setup. An arbitrary raster
operation cannot substitute for an echo. The runner does not add that operation
to someone else's service. A missing/incompatible echo limits execution coverage
and may cause setup or test failures; this alone does not establish that the
API violates Core. See the official [suite execution tests](https://github.com/opengeospatial/ets-ogcapi-processes10/blob/1.3/src/main/java/org/opengis/cite/ogcapiprocesses10/jobs/Jobs.java).

For an API exposed on the same Linux host:

```bash
python3 scripts/validate_cite_external.py \
  --base-url http://localhost:5001 \
  --echo-process echo \
  --network host
```

Or use `--network existing-network` to join a target's existing Docker network
and address it by its service hostname. The runner creates no networks, volumes
or API containers. It removes only its uniquely named validator container and
retains reports and the official image. Target containers and data are untouched
by runner cleanup; the suite's HTTP tests still exercise the target normally.
With default bridge networking, `localhost` refers to the validator itself.

Optional arguments:

- `--output-dir PATH`: parent directory for unique runs; default
  `runtime-data/cite-external/`, relative to the current working directory.
- `--timeout SECONDS`: execution timeout; default 900 seconds, followed by
  validator-container cleanup. Container creation/image pull has a separate
  300-second timeout.
- `--network NAME`: an existing Docker network or `host`; default `bridge`.

The first version targets APIs reachable without authentication and with normal
TLS trust. It adds no credentials, arbitrary request headers or insecure TLS
bypass. HTTP/private-network targets are permitted for deliberate local testing;
this CLI has no effect on our application's referenced-input SSRF restrictions.

## Reports and verdicts

Each `ogc-processes-cite-<id>/` run directory contains:

- **Official HTML:** `reports/testng/<run-id>/result/index.html`, with per-test
  pages, execution details and local JavaScript/styles.
- **Shareable HTML:** `official-report.zip`. Extract it and open `index.html`.
  This packages the unchanged official report while preserving asset paths;
  the pinned engine's own ZIP flattens those directories.
- **Native evidence:** TestNG XML, EARL and the engine's original `result.zip`
  alongside the HTML directory, retained unchanged.
- **Run information:** `summary.json`, `metadata.json`, the effective
  `test-run-props.xml`, execution/create/cleanup logs and any infrastructure error.

The script prints the report paths and pass/fail/skip counts. Some official
source/Javadoc links require TEAM Engine's web application and do not work
offline. No web server is needed to read the local results themselves.

Exit codes are **0** for a complete run with no failed tests/configuration,
**1** for actual suite/configuration failures, **2** for execution/report/cleanup
problems, and **130** for an interrupted run. Missing, inconsistent or entirely
skipped test reports never count as success. Native skips are preserved and do
not imply that every advertised feature was tested.

The runner requests descriptions for all processes and leaves test verdicts to
the official suite. It does not suppress failures or correct the target's
responses. ETS 1.3 has known schema ambiguities and synchronous-job assumptions;
review failures individually rather than treating either its score or a clean
run as OGC certification. Our service's [reviewed observations](../validation/cite-teamengine/current/README.md)
are useful context, not a baseline for another API.

Official resources: [TEAM Engine user guide](https://opengeospatial.github.io/teamengine/users.html),
[Processes suite 1.3](https://github.com/opengeospatial/ets-ogcapi-processes10/tree/1.3),
and the [executor's reporting support](https://github.com/opengeospatial/teamengine/blob/6.0.0-RC2/teamengine-spi/src/main/java/com/occamlab/te/spi/executors/testng/TestNGExecutor.java).
