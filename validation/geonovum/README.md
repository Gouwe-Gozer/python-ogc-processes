# Geonovum checker baselines

The reproducible workflow uses `@geonovum/ogc-checker` **1.3.2**, Processes
**1.0.0**, the pinned Node **24.22.1** image and the npm lockfile. Geonovum is
static OpenAPI analysis, not execution testing or certification.

## Default combined deployment

`job-list-baseline.json` is the default reviewed comparison for the Job List
implementation. Run `raster-geonovum-150b5f8f1dcc` removed the old missing-`/jobs`
finding and added exactly one finding:

- `/req/job-list/duration-definition#maxDuration`: checker expects a different
  array serialization from the advertised `style: form, explode: false`.

This is a **checker limitation**, not an accepted application defect.
[Requirement 74](https://docs.ogc.org/is/18-062r2/18-062r2.html#req_job-list_duration-definition)
explicitly specifies `explode: false` for `maxDuration`. The pinned checker's
`jobListParameter` rule omits that setting; `standards-checker`'s `hasParameter`
therefore applies the OpenAPI array default `true` and compares it with `false`.
A direct invocation of the installed function rejects `false` and accepts `true`;
the reproduction is retained in `runtime-data/validation/job-list-parameter-check.jsonl`.
The service accepts comma-separated and repeated values; no checker code or valid
parameter declaration was changed to hide the finding.

The other array parameters advertise their normative repeated-key defaults.
All required filters, result schemas, links and limits have HTTP/PostgreSQL tests;
both official CITE Job List methods pass. Geonovum only analyzes OpenAPI.

This is an explicit evidence-based baseline addition. The earlier
`combined-baseline.json` (one missing optional Job List finding) and `baseline.json`
(eight synchronous-profile findings) remain unchanged as historical comparisons.
The original combined work resolved seven missing async/status/results responses
through implemented worker behavior. Normal commands never update baselines.

## Run

```bash
make validate-geonovum
```

The default now builds an isolated combined API/PostgreSQL/worker stack, runs
synchronous and async info/warp/download smoke checks, then evaluates the live
OpenAPI against the Job List baseline. Reports, effective configuration and logs
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

A match returns 0 despite the reviewed checker limitation; it is a
regression check, not a compliance pass. Mismatches return 1, incomplete checker
runs return 2. Full diagnostic fields, sources and rulesets remain significant.
Only sources exactly matching the tested URL normalize to `<input>`. Transient
network/schema-resolution errors must not become accepted diagnostics.

Neither Make nor CI updates baselines automatically. Inspect every changed
finding and its applicability before an explicit update. Historical runtime
source differences and the locked checker upgrade are documented in
[upgrade-1.3.2.md](upgrade-1.3.2.md). The [validation guide](../../docs/validation.md)
records the current coverage boundary.
