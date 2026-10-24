# Geonovum checker baseline

The reviewed report uses `@geonovum/ogc-checker` **1.2.0**, the OGC API –
Processes **1.0.0** profile, Node **24** and npm **11.6.0**. It was rechecked
against the Rasterio release on **2026-10-24**. This is static OpenAPI analysis;
it neither executes rasters nor certifies conformance.

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

With Node 24/npm 11.6.0 available:

```bash
uv run python scripts/check_geonovum_baseline.py --input 'http://127.0.0.1:5001/openapi?f=json'
```

Use `--raw-output runtime-data/geonovum-checker.json` to retain a raw report
(create the parent directory first). Only a deliberate review should use
`--update-baseline`; never update it automatically to make CI pass. The runner
retries incomplete network/schema fetches and reports operational failures
separately. CI runs this comparison on pull requests/manual dispatches, not
ordinary pushes to `main`.

## Diagnostic sources

The runner normalizes only a diagnostic source exactly matching the tested URL
to `<input>`. All other sources, rulesets and diagnostic fields remain significant;
mismatch messages include the source.

A historical CI failure showed the same five findings as both added and removed.
With checker 1.2.0/npm 11.6.0, a local Node 20.20.2 run used conformance URIs as
sources; Node 24.22.1 used the tested OpenAPI URL and matched the baseline after
normalization. Moving CI to Node 24 resolved that reproduced mismatch without
relaxing comparison or changing capabilities. Action runtimes and the checker
runtime are configured separately in the workflow.
