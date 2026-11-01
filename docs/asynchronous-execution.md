# Durable asynchronous execution

The default deployment runs the API, PostgreSQL and one separate worker. It accepts `Prefer: respond-async`, persists the execution, and runs it
outside the API process. Existing processors, input security, output formats and
result-store limits are unchanged. No PostGIS extension is required.

## Start

Use [release deployment](release-image.md#run-and-inspect) for a self-contained
image or [development](development.md#container-and-integration-checks) for source
mounts. Both start API, PostgreSQL and worker.

For a database-free, synchronous-only API, apply `compose.sync.yml` after the
release file:

```bash
docker compose -f compose.release.yml -f compose.sync.yml up --build --detach
```

For bind-mounted development, use `-f compose.yml -f compose.sync.yml` instead.
This opt-out retains no jobs; see [capabilities and gaps](validation.md#conformance-claims-and-gaps).

Both result and database volumes survive normal `down`; `down --volumes` removes
both. Use one image/configuration for API and worker and a persistent, URL-safe
`GEO_JOB_PASSWORD` for hosted use. Compose supplies `GEO_JOB_DSN` from its
PostgreSQL credentials; host runs/tests need a reachable PostgreSQL DSN.
Job persistence details and access boundaries
are below; deployment/proxy settings belong in the release guide.

## Submit, poll and retrieve

Create a request using the existing examples or local-file client. For example:

```bash
curl -i -X POST http://localhost:5001/processes/raster-warp/execution \
  -H 'Content-Type: application/json' \
  -H 'Prefer: respond-async' \
  --data-binary @examples/warp-reference-request.json
```

The input must still be a valid inline base64 GeoTIFF or controlled public HTTPS
reference. Check the example's input before submitting your own data.

A successful submission returns **201**, `Preference-Applied: respond-async`, a
`Location` pointing to `/jobs/{jobID}`, and JSON containing `jobID`, `processID`, `type` and
`status`. No raster processing or remote-input download occurs in that HTTP
request. Referenced inputs are fetched when the worker executes the job, so
their URLs must remain usable until then. Omit the preference to retain the existing synchronous behavior; those
calls do not create retained jobs or a misleading job Location.

```bash
curl http://localhost:5001/jobs/JOB_ID
curl -i http://localhost:5001/jobs/JOB_ID/results
```

Pending status documents include a standard `monitor` link for polling; terminal
documents link to results. Status transitions are `accepted` → `running` → `successful` or `failed`.
Results return **404 / ResultNotReady** while pending, **404 / NoSuchJob** for
unknown/expired IDs, and the stored cause-specific error on failure (for example
400 for invalid input, 503 for exhausted processing capacity, 500 for interruption).

Successful result retrieval preserves the original `response` and output
transmission choices: JSON/TIFF/GeoJSON by value, document references, or an empty
204 with a `Link` header for raw/reference. Download links use the configured
public URL. The API does not render rasters, resolve internal artifact shortcuts,
or relax HTTPS/private-network restrictions for chaining.

All five processors use the same execution/formatting path and have container
coverage, alongside the independent custom-process example. Lifecycle tests cover
restart/interruption, failure contracts, capacity and expiry. Processors do not
implement their own async methods.

## List retained jobs

`GET /jobs` returns HTTP 200 with `jobs` (the same status documents as individual
job retrieval) and navigation `links`. JSON and native pygeoapi HTML are supported:

```bash
curl 'http://localhost:5001/jobs?f=json&processID=raster-warp&status=accepted,running&limit=5'
# Inclusive creation-time interval; .. or an empty endpoint opens that end:
curl 'http://localhost:5001/jobs?datetime=2026-10-31T00:00:00Z/..'
```

| Parameter | Meaning |
| --- | --- |
| `type` | Comma-separated job types; this service stores only `process` jobs |
| `processID` | Comma-separated process identifiers |
| `status` | Comma-separated states, such as `accepted,running` or `successful,failed` |
| `datetime` | RFC 3339 creation instant or inclusive interval; timestamps require timezones |
| `minDuration`, `maxDuration` | Integer execution seconds, inclusive; running jobs use time since start, completed jobs use finish minus start |
| `limit` | Default 10, maximum 50 under the current server limits; larger requests are throttled |
| `offset` | Nonnegative pagination offset, default 0 |
| `f` | `json` or `html` |

Values within `type`, `processID` and `status` combine with OR; different filters
combine with AND. Repeated array parameters are accepted as well as comma-separated
values. Section 11 declares duration parameters as integer arrays without defining
how multiple bounds combine; every supplied bound applies here (strongest minimum
and strongest maximum). Duration-filtered lists omit jobs without the necessary
start/finish timestamps, including accepted jobs. Unfiltered lists include accepted
jobs. Invalid query syntax returns 400; unknown IDs/types/states select no matches.

Only unexpired asynchronous jobs are listed, ordered by creation time then job ID.
Follow `next`/`prev` links, which preserve filters and the effective limit;
`self`/`alternate` links are present in the body and HTTP Link header. Offsets do not
provide a snapshot: concurrent expiry or state changes can change later pages.
Job responses use `Cache-Control: no-store`.

**Access boundary:** this application has no authentication or per-user job ownership.
Job IDs and status metadata are discoverable to anyone who can access `/jobs`.
The list never includes request inputs, stored result bodies or internal paths;
status/result URLs retain their existing access behavior. Protect the whole API
consistently at deployment if data or job metadata must be private. This feature
does not introduce an authorization model.

## Persistence and interruption

`DurableProcessManager` extends pygeoapi 0.24.0's `PostgreSQLManager`. It retains
native registration and the `jobs` metadata table. Two application-owned TEXT
columns on that same table store JSON-encoded requests and complete formatted
responses, including binary bytes encoded as base64, status and headers. The
application database user must own that dedicated table and be able to create/
alter it. Do not share this table with a stock manager writing unrelated jobs.

A single worker per dedicated job database holds a PostgreSQL session advisory lock, claims one accepted
job transactionally, and executes it in a fresh child process. Child processes
open independent Rasterio datasets and retain the existing staging/publication
locks. Each child has a wall-clock deadline; shutdown/timeout kills and reaps it.
A second worker is rejected rather than creating unbounded concurrency.

- API restarts do not stop the separate worker or discard queued work/results.
- Accepted requests remain queued across worker/database restarts.
- On worker restart, abandoned `running` jobs become explicitly failed. There
  are no automatic retries, resumption or exactly-once guarantees for interrupted
  computation. A late child cannot overwrite a failed job's terminal state.
- Database loss stops the worker; Compose restarts it. An in-flight job is
  treated as interrupted. API database errors return 503 for job retrieval.
- A crash after file publication can leave an unreferenced bounded file. Existing
  result-store expiry and abandoned-workspace cleanup reclaim it. Persistent
  volumes and database backups remain deployment responsibilities.

## Bounds and lifetime

| Setting | Default | Allowed range and meaning |
| --- | ---: | --- |
| `GEO_JOB_MAX_COUNT` | 16 | 1–1,000 retained async jobs, including completed/failed jobs |
| `GEO_JOB_MAX_BYTES` | 64 MiB | 1 byte–1 GiB total retained request/response budget; failure headroom is reserved |
| `GEO_JOB_TIMEOUT` | 30 seconds | **1–300 seconds**, including child initialization and processing |
| `GEO_RESULT_RETENTION_SECONDS` | 86400 | 1 second–7 days; also bounds job lifetime from acceptance |

These settings apply to the whole deployment, not individual processors. The
300-second ceiling remains enforced in `async_manager.job_limits()`. One worker
executes one job at a time; every job starts a fresh child, so process-local model
caches are not retained between jobs. CPU/RAM, scratch storage and dependency
constraints are mapped in [resource configuration](release-image.md#resource-configuration).

Expired job rows are removed during admission and worker queue polling. They are never exposed
after expiry. Jobs are not retained longer than their referenced raster files;
file publication occurs after acceptance and uses the same retention duration.
Increasing file retention or job settings requires appropriate disk/memory
capacity. PostgreSQL's own storage, indexes/WAL and normal maintenance add overhead
outside the payload budget. Input/request/raster and file-store limits remain
independent and unchanged. Small retention settings can expire queued work;
choose a retention window longer than expected queue wait and execution time.

## Scope and verification

The durable manager supports the optional Job List class, including its Section 11
filters and pagination. Discovery and OpenAPI advertise it only for that manager;
the synchronous opt-out does not claim Job List. No callbacks, dismissal, progress,
retries, distributed queue or workflow chaining are supplied. Job DELETE remains
405. OpenAPI includes listing and 201/status/result responses for the durable manager. Core has no separate async conformance class; the existing intended
Core alignment remains subject to the documented limitations and external review.

Relevant Core 1.0 clauses: [Requirements 25–26, 34–46 and Section 11 (64–79)](https://docs.ogc.org/is/18-062r2/18-062r2.html).
Stock pygeoapi starts API-local threads, lacks durable request handoff, does not
call our result formatter, emits a job Location on synchronous calls when the
manager is async, and simplifies result/error responses. The narrow manager/HTTP
adapters correct these boundaries without patching pygeoapi or introducing a
second job store. Callback claims still follow the manager's subscriber flag,
which is false here; no additional certification claim is made.

```bash
# Manager/HTTP tests create isolated schemas in a disposable PostgreSQL database.
GEO_TEST_JOB_DSN=postgresql://USER:PASSWORD@localhost:5432/TEST_DB \
  uv run pytest tests/test_async_manager.py tests/test_job_list.py -v

# Builds the real release image and creates/removes only raster-async-test-* resources.
GEO_TEST_ASYNC_CONTAINERS=1 uv run pytest tests/test_async_containers.py -v
```

The container tests include actual API/database restarts, successful TIFF
retrieval/downloads after restart, worker SIGKILL recovery, deadlines and retained
input-security checks. The fixture's slow process exists only in test config.
Default Geonovum and CITE workflows now start isolated copies of this combined
deployment, run synchronous and async raster smoke checks, and then execute the
official validators. See [validation](validation.md) for current findings and
coverage limits.
