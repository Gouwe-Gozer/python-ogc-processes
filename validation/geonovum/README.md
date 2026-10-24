# Geonovum checker baseline

The reviewed report uses `@geonovum/ogc-checker` **1.2.0**, the OGC API –
Processes **1.0.0** profile, Node **24** and npm **11.6.0**. It was rechecked
against the Rasterio release on **2026-10-24**. This is static OpenAPI analysis;
it neither executes rasters nor certifies conformance.

## Reviewed diagnostics

The baseline retains five error diagnostics about the OpenAPI document:

- `/req/core/job`: no description of `/jobs/{jobID}`;
- `/req/core/job-results`: no description of `/jobs/{jobID}/results`;
- `/req/core/process-execute-success-async`: no asynchronous 201 response for
  each of the two synchronous public processes (two diagnostics);
- `/req/job-list/job-list-op`: no description of `/jobs`.

These are observed checker findings, not a reason to advertise unimplemented
async or Job List support. They do not establish that Flask has no job routes;
the existing runtime routes need their own behavior checks. The distinction
between public declarations, Core gaps and optional capabilities is explained in
[validation](../../docs/validation.md#conformance-claims-and-gaps).

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
