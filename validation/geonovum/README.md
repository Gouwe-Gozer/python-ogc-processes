# Geonovum checker baselines

The workflow pins `@geonovum/ogc-checker` **1.3.2**, Processes **1.0.0**,
Node **24.22.1** by image digest and npm dependencies through `package-lock.json`.
This is static OpenAPI analysis, not execution testing or certification.

## Reviewed findings

[`job-list-baseline.json`](job-list-baseline.json) is the default exact comparison.
It records one diagnostic: `/req/job-list/duration-definition#maxDuration`.
[Requirement 74](https://docs.ogc.org/is/18-062r2/18-062r2.html#req_job-list_duration-definition)
explicitly requires `style: form, explode: false`, as advertised by this service.
The pinned checker's `jobListParameter` rule omits `explode`, so its parameter
comparison applies the OpenAPI default `true` and rejects the normative `false`.
This was independently reproduced by invoking the installed comparison with
both values. The reviewed diagnostic is a **checker limitation**, not an accepted
application defect. Do not change the valid declaration to silence it.

The service accepts comma-separated/repeated values and has HTTP/PostgreSQL
coverage for all required Job List filters, pagination, schemas and links.
Both CITE Job List methods pass; Geonovum alone cannot establish that behavior.

[`baseline.json`](baseline.json) remains an explicit comparison for the supported
synchronous-only opt-out: seven conditional retained-job/async success expectations
and one unadvertised optional Job List expectation. It is not the default or a
description of the durable deployment. Normal commands never update either file.

## Run

```bash
make validate-geonovum
```

The default builds an isolated API/PostgreSQL/worker stack, runs synchronous and
async info/warp/download smokes, then compares live OpenAPI with the Job List
baseline. Reports/configuration/logs remain under `runtime-data/geonovum/`.
Only that generated project's resources are removed; existing deployments are
untouched. Node/npm come from Docker, not the host.

To check an already running combined service:

```bash
make validate-geonovum GEONOVUM_INPUT='http://127.0.0.1:5001/openapi?f=json'
```

This override runs only the checker and writes `runtime-data/validation/geonovum.json`.
For an explicitly started synchronous-only service, select its baseline:

```bash
uv run python scripts/check_geonovum_baseline.py --docker \
  --input 'http://127.0.0.1:5001/openapi?f=json' \
  --baseline validation/geonovum/baseline.json
```

A match returns 0 despite reviewed findings; mismatches return 1 and incomplete
checker runs return 2. Full diagnostic fields, source identities and rulesets
remain significant. Only sources exactly matching the tested URL normalize to
`<input>`. Network/schema-resolution errors must not become accepted findings.

Inspect every changed diagnostic against the standard and actual behavior before
an explicit baseline update. Neither Make nor CI updates baselines automatically.
See [validation](../../docs/validation.md) for current claims and coverage limits.
