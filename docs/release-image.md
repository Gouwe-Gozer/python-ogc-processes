# Release image

The application builds on the official `geopython/pygeoapi:0.24.0` image,
pinned by manifest digest in `docker/Dockerfile`. Terrio 0.4.2 is installed using
`/venv/bin/python3 -m pip` inside the image, with wheel-only installation. The
same `/venv` interpreter runs Gunicorn and imports the configured processor.
No host Python packages or OS packages are installed.

The processing adapter uses Terrio's native binding without a GDAL backend.
The inherited pygeoapi environment still includes Rasterio; this image is not
claimed to be GDAL-free. The approved [pivot](rasterio-pivot.md) will remove
Terrio and use Rasterio directly; this section describes the current image.

The owned entrypoint generates the corrected OpenAPI document in `/tmp`, then
execs Gunicorn with two synchronous workers and a 30-second worker timeout.
`WSGI_WORKERS` and `WSGI_WORKER_TIMEOUT` can be overridden. The upstream image's
base dependencies are fixed by its digest; they are not all identical to the
local uv lockfile. The pygeoapi and Terrio versions match in both environments.

The release Compose service has no host bind mounts. It has one writable named
volume, mounted at `/var/lib/terrio/results`, for persistent bounded outputs.
The image seeds that directory with UID/GID 10001 ownership before dropping
privileges; no runtime root initialization is required. The service runs as UID/GID 10001,
with a read-only root, a 64 MB `/tmp` tmpfs, all Linux capabilities dropped and
`no-new-privileges`. A health check fetches `/conformance`. The smoke script
also executes the raster process, and the isolation checker inspects Docker's
actual runtime settings.
Release Compose also caps memory at 512 MiB, CPU at one core and process count
at 128. A shared volume lock allows one warp at a time across workers, while
downloads can proceed. See [result storage](results.md) for application limits.

```bash
docker compose --file compose.release.yml up --build --detach
uv run python scripts/smoke_discovery.py --base-url http://localhost:5001
uv run python scripts/smoke_warp.py --base-url http://localhost:5001
uv run python scripts/check_release_container.py
docker compose --file compose.release.yml exec -T api /venv/bin/python3 -c 'import terrio, pygeoapi; from terrio_processes.processes.info import TerrioInfoProcessor; print(terrio.__version__, pygeoapi.__version__)'
```

Result URLs are built from `PYGEOAPI_SERVER_URL`, not the requesting Host header.
Set it to the client-facing address when running behind a proxy or on another
port. The named volume retains results when the service is restarted or
recreated. A normal `docker compose down` preserves it; `down --volumes` deletes
the results. Cleanup removes expired files without evicting unexpired outputs.

This remains a local prototype without authentication, TLS termination or
production deployment automation. Result download URLs are opaque, but are
accessible to anyone who has them until expiry.
