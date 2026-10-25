# Geonovum checker baseline

The reviewed report uses `@geonovum/ogc-checker` **1.3.2**, the approved OGC API –
Processes **1.0.0** profile, Node **24.22.1** and npm **11.19.1**. The pinned Node
image and npm lockfile make the normal local/CI workflow reproducible without
host Node installation. This is static OpenAPI analysis; it neither executes
rasters nor certifies conformance. The [upgrade review](upgrade-1.3.2.md) records
why the existing eight findings remain unchanged.

## Reviewed diagnostics

The baseline retains eight error diagnostics about the OpenAPI document:

- `/req/core/job-success`: no successful job-status 200 response;
- `/req/core/job-results-async-document`: no successful job-results 200 response;
- `/req/core/process-execute-success-async`: no asynchronous 201 response for
  each of the five synchronous public processes (five diagnostics);
- `/req/job-list/job-list-op`: no description of `/jobs`.

These are observed checker findings, not a reason to advertise unimplemented
async or Job List support. The public manager retains no jobs, so the existing
job routes return the tested, prescribed unknown-job 404 for every identifier.
Permission 7 makes synchronous job creation optional; no successful job retrieval
can currently occur. OpenAPI describes actual responses instead of inventing
reachable 200/201 behavior. The applicability analysis is in the
[Core audit](../../docs/core-conformance-audit.md). The general evidence boundary is in
[validation](../../docs/validation.md#conformance-claims-and-gaps).

The Core audit replaced two missing-path findings (`/req/core/job` and
`/req/core/job-results`) with the two successful-response findings above. All
other diagnostics and checker metadata were unchanged. This exact change was
reviewed against the running release before updating `baseline.json`; the runner
and its normalization/comparison rules were not relaxed.

Adding sample-points, reclassify and polygonize then added exactly three
`/req/core/process-execute-success-async` findings, one per new synchronous
execution route. A Node 24/npm 11.6.0 run against the self-contained release
confirmed all five earlier diagnostics and checker metadata were unchanged,
with no transient schema-fetch failures. The baseline was extended to eight;
no asynchronous responses were added to the advertised contract.

## Compare a running service

With Docker, Make and the project uv environment available, start the service
as described in the README, then:

```bash
make validate-geonovum
make validate-geonovum GEONOVUM_INPUT='http://127.0.0.1:5002/openapi?f=json'
```

The default command uses the pinned Node container and `npm ci` with
`package-lock.json`. It needs Linux Docker host networking (or Docker Desktop
host networking enabled). Reports are written to
`runtime-data/validation/geonovum.json`; npm caches/logs and installed checker
packages remain ignored. No application result volume is touched. Container
cleanup is scoped to a generated name, including after a checker timeout.

The existing standalone script also supports native `npx` invocation with the
exact package version for diagnostics; the Docker/Make path is the reproducible
locked workflow used by CI. Operational failures return 2; baseline mismatches
return 1. An exact match returns 0 even though the retained raw report still
contains eight errors. It is a regression baseline, not a compliance pass.

Inspect code/path/source, conformance-class `ruleset`, severity and message
changes before deliberately updating the baseline. Never run `--update-baseline`
automatically in Make or CI. The 1.3.2 change is limited to version/class metadata;
no new diagnostic is silently accepted. Pull requests and manual normal-CI
runs preserve the raw report as an artifact, including successful comparisons.

## Diagnostic sources

The runner normalizes only a diagnostic source exactly matching the tested URL
to `<input>`. All other sources, rulesets and diagnostic fields remain significant;
mismatch messages include the source.

A historical CI failure showed the same five findings as both added and removed.
With checker 1.2.0/npm 11.6.0, a local Node 20.20.2 run used conformance URIs as
sources; Node 24.22.1 used the tested OpenAPI URL and matched the baseline after
normalization. Moving CI to Node 24 resolved that reproduced mismatch without
relaxing comparison or changing capabilities. The current locked Docker workflow replaces that host-runtime ambiguity.
