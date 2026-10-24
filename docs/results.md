# Raster results and lifecycle

`raster-warp` writes the demo or validated [user inputs](inputs.md) to GeoTIFF. All executions create a
stored result, including requests that return the raster by value. The public
output identifier is `result`. No persistent OGC job resource is created.

## HTTP contract

| Request | Status | Content |
| --- | --- | --- |
| `response: raw`, value transmission | 200 | Native `image/tiff`, attachment `output.tif` |
| `response: document`, value transmission | 200 | JSON `{"result":{"value":"...base64...","encoding":"base64","mediaType":"image/tiff"}}` |
| `response: document`, reference transmission | 200 | JSON `{"result":{"href":"http://.../results/<id>/output.tif","type":"image/tiff"}}` |
| `response: raw`, reference transmission | 204 | Empty body; `Link` header containing the result URL and `image/tiff` type |

Omitted response means raw; omitted outputs means the defined `result` output;
omitted transmission means value. Document mode does not silently change value
to reference. `Prefer: respond-async` is ignored without a misleading applied
preference or job location. Unsupported formats and identifiers return JSON 400.

Reference URLs use the configured `PYGEOAPI_SERVER_URL`, including its path
prefix, independently of the incoming Host header. It must be an absolute HTTP
or HTTPS URL reachable by the client. The API never returns a container path.
GET `/results/<id>/output.tif` returns `image/tiff`, an attachment filename,
`Cache-Control: no-store`, and an `Expires` timestamp. Invalid, missing and
expired IDs return JSON 404. Internal storage failures return sanitized JSON 500.

## Storage and expiry

Development and release Compose mount the named volume `results` at
`/var/lib/geo/results`. New volumes inherit UID/GID 10001 ownership from the
image. No runtime root process is needed, and the rest of the release root
filesystem remains read-only. Files survive container restart and recreation;
a normal Compose `down` retains the volume. `down --volumes` deletes all results.

The initial retention period is **86,400 seconds (24 hours)** after successful
publication. Download checks enforce expiry on every request. A restart does
not reset a file's age. Operator changes to the retention setting apply to
existing files as well as new ones; volume deletion or storage failure can
remove files before their normal expiry.

Expired files and abandoned workspaces are physically removed before the next
warp or during explicit cleanup. This is lazy cleanup: files may remain on disk
while the service is idle, but expired download URLs already return 404. There
is no background job system. To clean the running release volume explicitly:

```bash
docker compose --file compose.release.yml exec -T api \
  /venv/bin/python3 -m geo_processes.storage cleanup
```

For locally generated files outside Docker, use:

```bash
uv run python -m geo_processes.storage cleanup
```

Local Python defaults to `runtime-data/results` under the current repository;
set `GEO_OUTPUT_DIR` when using another approved working directory. Storage
locking uses Linux `flock`; run locally on Linux or use Docker.

## Bounds and configuration

Compose passes these settings from the environment or `.env`:

| Variable | Default | Accepted range |
| --- | --- | --- |
| `GEO_RESULT_RETENTION_SECONDS` | `86400` | 1 second to 7 days |
| `GEO_RESULT_MAX_BYTES` | `67108864` (64 MiB) | 1 byte to 1 GiB |
| `GEO_RESULT_MAX_COUNT` | `256` | 1 to 10,000 results |

Compose fixes `GEO_OUTPUT_DIR` to the volume mount. The one active writer
uses an additional staging file; the byte quota and 16 MiB output limit are
checked after writing and before publication. These are application publication
bounds, not filesystem quotas for staging or files an operator places in the
volume. Input byte/sample/decode limits and the fixed grid bound the current operation.
The service never evicts unexpired results to accept a
new execution. A busy writer or full store returns JSON **503**; retry when the
writer completes, files expire, or capacity is deliberately increased.

Each output is written in a private per-request workspace, checked against a
16 MiB file limit and the store quota, then atomically renamed to an opaque
UUID filename. Failed writes clean their workspaces. The next writer cleans
workspaces left by interrupted workers. Readers refuse symlinks, special files
and invalid IDs; publication is serialized across the two Gunicorn workers
sharing this local volume. Downloads can proceed during another warp.

Both info and warp inputs are limited to 16 MiB and 1,048,576 samples including bands. Warp
retains source width and height, bounding the target sample count. Requests are
limited to 24 MiB for base64 inputs; clients cannot choose resolution, dimensions or extents.
The release uses two synchronous Gunicorn workers with a 30-second worker
timeout and container limits of 512 MiB RAM, one CPU and 128 processes. A killed
worker may leave an unpublished workspace, which the next writer removes.

User inputs arrive through HTTPS references or inline base64; `demo-dem` remains
registered in `datasets.py`. Input staging uses separate temporary slots and is
removed after execution. Reusable uploads, object storage, distributed workers,
authentication and additional operations remain future work; see
[inputs](inputs.md) and the [roadmap](roadmap.md).
