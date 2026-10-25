# Async readiness review — 2026-10-25

Reviewed the synchronous service at `2f6cae1` against installed pygeoapi 0.24.0.
The next milestone is asynchronous submission, status tracking and result
retrieval using pygeoapi's PostgreSQL manager and in-process execution. No async
implementation, dependency change or new job infrastructure is part of this review.

The independent processors, Rasterio adapters, controlled input resolver and
bounded result store can be retained. The blockers below belong in the async
milestone; a preliminary processing-framework rewrite is unnecessary.

## Blockers before advertising async

| Area | Finding and required action |
| --- | --- |
| Result and error integration | [`manager.py`](../src/geo_processes/manager.py) supplies the public result URL, calls processor `format_result()` and unwraps `ProcessResponse`; the stock base handler does none of these. Four processors return [`FileOutput`](../src/geo_processes/delivery.py), which is not a stock persistable result. Integrate serializable job results while preserving JSON/TIFF/GeoJSON, output IDs, raw/document and value/reference behavior. Preserve typed, sanitized failures: the stock handler collapses exceptions, and the job-results route reports every failed job as a generic 400. |
| Job and file lifetime | [`storage.py`](../src/geo_processes/storage.py) expires files independently of jobs. The synchronous manager does not persist job response files; only `GEO_OUTPUT_DIR` has a persistent release volume. Choose an explicit persistent manager output directory for async and coordinate cleanup of job records, job response files and referenced results. Define interrupted-job behavior; database persistence does not resume a background thread. |
| Bounded execution and state | Upstream starts a thread per accepted async request, without an admission cap. Its handler only writes `running` after `processor.execute()` returns. Add bounded admission and meaningful running/failure transitions, and handle worker interruption. Existing two input slots and the single nonblocking result writer remain useful limits, but do not bound background thread creation. |
| PostgreSQL integration evidence | [`pyproject.toml`](../pyproject.toml)/`uv.lock` contain SQLAlchemy transitively but no `psycopg2` driver; the local driver is absent, although it is available in the pinned release base. Declare the required driver for reproducible local tests and verify the release version rather than installing it twice. Add a real PostgreSQL integration test/Compose setup, including database readiness during startup/OpenAPI generation, which instantiates the manager. No PostGIS extension is needed for job metadata. |

Use upstream PostgreSQL job CRUD, registration and routes. Limit application
integration to the representation, validation, admission and lifecycle behavior
that upstream does not supply. Do not add a second job table or a parallel scheduler.

Tests must exercise asynchronous acceptance, polling, successful JSON/TIFF/GeoJSON
retrieval, reference downloads, failures, pending/unknown results, capacity,
restart and expiry. Current [`test_core_conformance.py`](../tests/test_core_conformance.py)
uses TinyDB to check job errors, and [`test_openapi_patch.py`](../tests/test_openapi_patch.py)
preserves its generated success responses. Neither establishes raster async readiness.

Revisit process capabilities and all job-related claims together. Discovery now
uses the API instance manager's native `supports_subscribing` flag for Callback,
independently of async support; manager construction no longer changes global
declarations. The public request guard still rejects subscribers. A future
manager change must reconcile that guard with the advertised capabilities;
changing the manager alone does not enable public callbacks or dismissal.
The stock manager also retains synchronous jobs; decide
whether to retain that behavior and provide monitor links when applicable.

The [Core standard](https://docs.ogc.org/is/18-062r2/18-062r2.html), Requirements
25–26 and 33–46, governs negotiation, acceptance, status, results and failures.
Use its official [process description](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/ProcessDescription.json)
and [execute](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/Execute.json)
examples alongside the schemas. Extend the unchanged offline snapshot with the
job-status schemas when testing the new capability; keep the existing binary
schema caveat explicit. See [validation](validation.md).

Upstream sources inspected:
[`BaseManager`](https://github.com/geopython/pygeoapi/blob/0.24.0/pygeoapi/process/manager/base.py),
[`PostgreSQLManager`](https://github.com/geopython/pygeoapi/blob/0.24.0/pygeoapi/process/manager/postgresql.py)
and [process routes](https://github.com/geopython/pygeoapi/blob/0.24.0/pygeoapi/api/processes.py).
These are source-review findings; no PostgreSQL raster execution was run.

## Worthwhile cleanup

- **Applied in this review:** prune the eight unused generic OpenAPI tag
  declarations, preserving paths, operation groupings and retained tag metadata.
  Update the canonical service description and README to explain intended OGC
  alignment, all five operations and the sync/async distinction.
- **Documentation:** development, result delivery, operation examples and Docker
  instructions remain consistent with current behavior. Correct the input guide's
  two-process wording and validation's suggestion that object inputs are future
  work. Record the chosen next milestone in [the roadmap](roadmap.md).
- **Completed boundary cleanup:** shared processor input/execution exceptions
  live in `errors.py`, independent of the manager. This removes the import
  coupling; the result-format and job-lifecycle integration above still remains.
- **Deployment:** preserve the explicit worker/time/memory budgets in
  [`entrypoint.sh`](../docker/entrypoint.sh) and [release Compose](../compose.release.yml).
  The current 30-second Gunicorn request timeout is not an async job timeout.
  Define shutdown and job limits explicitly rather than assuming the database
  or existing synchronous timeout provides them.

## Optional improvements

- Independent workers, a queue, object storage, automatic retries and horizontal
  scaling can wait. They are not prerequisites for the proposed single-instance
  milestone. Keep the existing one-writer policy initially and document busy
  failures; avoid a concurrency rewrite without workload evidence.
- Improve navigation among process descriptions, examples and sample data if
  client testing shows users need it. The current examples and local-file client
  are usable; external GUI behavior remains tracked in [the client log](client-interoperability.md).
- Add the AHN4 sample's original download source and reuse attribution once
  confirmed. [Sample data](sample-data.md) currently records the supplied filename,
  checksum and alignment, but not a source dataset licence. Do not infer it from
  the code's MIT licence.
