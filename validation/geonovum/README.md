# Geonovum checker baselines

The reproducible workflow uses `@geonovum/ogc-checker` **1.3.2**, Processes
**1.0.0**, the pinned Node **24.22.1** image and the npm lockfile. Geonovum is
static OpenAPI analysis, not execution testing or certification.

## Default combined deployment

`combined-baseline.json` records one reviewed finding:

- `/req/job-list/job-list-op`: no `/jobs` listing operation is advertised.

Job List is an optional extension intentionally excluded from this service.
Async submission and individual job status/results are implemented; listing,
dismissal and callbacks are not. This retained finding is not a missing Core
execution/status/results operation.

The combined run resolved seven findings from the historical synchronous
baseline: five missing 201 responses, missing job-status 200 and missing
job-results 200. No diagnostics were added. Those responses are backed by real
worker execution and HTTP tests, not fabricated declarations. The original
`baseline.json` remains unchanged as the explicit synchronous-profile record.

## Run

```bash
make validate-geonovum
```

The default now builds an isolated combined API/PostgreSQL/worker stack, runs
synchronous and async info/warp/download smoke checks, then evaluates the live
OpenAPI against the combined baseline. Reports, effective configuration and logs
are retained under `runtime-data/geonovum/`. Only that generated project's
containers/network/volumes/image are removed. Existing deployments are untouched.

To evaluate an already running combined service, including normal CI:

```bash
make validate-geonovum GEONOVUM_INPUT='http://127.0.0.1:5001/openapi?f=json'
```

That explicit override runs only the checker and writes
`runtime-data/validation/geonovum.json`. To compare a lightweight synchronous
service with its historical baseline:

```bash
uv run python scripts/check_geonovum_baseline.py --docker \
  --input 'http://127.0.0.1:5001/openapi?f=json' \
  --baseline validation/geonovum/baseline.json
```

A match returns 0 despite the reviewed optional-extension finding; it is a
regression check, not a compliance pass. Mismatches return 1, incomplete checker
runs return 2. Full diagnostic fields, sources and rulesets remain significant.
Only sources exactly matching the tested URL normalize to `<input>`. Transient
network/schema-resolution errors must not become accepted diagnostics.

Neither Make nor CI updates baselines automatically. Inspect every changed
finding and its applicability before an explicit update. Historical runtime
source differences and the locked checker upgrade are documented in
[upgrade-1.3.2.md](upgrade-1.3.2.md). The [validation guide](../../docs/validation.md)
records the current coverage boundary.
