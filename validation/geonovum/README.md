# Geonovum checker baseline

Updated on **2026-10-23** against the running Geo Processes release container,
pygeoapi 0.24.0, Rasterio 1.4.3 and NumPy 1.26.4. `@geonovum/ogc-checker` **1.2.0** used the
OGC API – Processes **1.0.0** profile. This checks OpenAPI statically; it does
not execute Terrio or certify conformance.

The latest run, including `terrio-warp`, completed with **five error diagnostics**:

- `/req/core/job`: no `/jobs/{jobID}` resource;
- `/req/core/job-results`: no `/jobs/{jobID}/results` resource;
- `/req/core/process-execute-success-async`: no asynchronous 201 response for
  each of the two public synchronous processes (two diagnostics);
- `/req/job-list/job-list-op`: no `/jobs` resource.

The earlier Terrio warp milestone added the fifth diagnostic. The Rasterio
pivot was checked against the new running service: only the two execution paths
change to `/processes/raster-info/execution` and `/processes/raster-warp/execution`.
Rulesets, messages, severities and all other diagnostic fields are unchanged.

These are recorded limitations of the bounded synchronous service. Its public
contract does not promise async jobs or Job List conformance. No optional
endpoint was added solely to satisfy a static checker. Raw and document
execution are separately tested against HTTP and the official OGC schemas.

The latest checker uses the tested document URL as diagnostic `source`.
The runner normalizes only an exact match of that URL to `<input>`, making
port 5001/5002 runs comparable; other sources and all diagnostic fields remain
significant. The original raw report remains available when `--raw-output` is
requested. Rulesets and diagnostic changes are still compared exactly.

With Node/npm available, compare or deliberately update the baseline:

```bash
uv run python scripts/check_geonovum_baseline.py --input 'http://127.0.0.1:5001/openapi?f=json'
uv run python scripts/check_geonovum_baseline.py --input 'http://127.0.0.1:5001/openapi?f=json' --update-baseline
```

Never update the baseline automatically in CI. A newly added, removed or changed
diagnostic requires review. The runner retries incomplete network/schema fetch
attempts and reports operational failures separately.

This development environment had no host Node installation. The completed run
used a disposable container, without installing Node/npm on the host:

```bash
docker run --rm --network host node:24-alpine \
  npx --yes @geonovum/ogc-checker@1.2.0 validate \
  --standard ogc-api-processes --version 1.0.0 \
  --input 'http://127.0.0.1:5004/openapi?f=json' --format json --fail-on none
```

The JSON report was normalized by the same `normalize_report` function used by
the runner. This records an observed diagnostic set, not a passing checker result.
