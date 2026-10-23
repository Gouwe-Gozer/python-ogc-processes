# Release image

The application builds on the official `geopython/pygeoapi:0.24.0` image,
pinned by manifest digest in `docker/Dockerfile`. Terrio 0.4.2 is installed using
`/venv/bin/python3 -m pip` inside the image, with wheel-only installation. The
same `/venv` interpreter runs Gunicorn and imports the configured processor.
No host Python packages or OS packages are installed.

The owned entrypoint generates the corrected OpenAPI document in `/tmp`, then
execs Gunicorn with two synchronous workers and a 30-second worker timeout.
`WSGI_WORKERS` and `WSGI_WORKER_TIMEOUT` can be overridden. The upstream image's
base dependencies are fixed by its digest; they are not all identical to the
local uv lockfile. The pygeoapi and Terrio versions match in both environments.

The release Compose service has no host mounts. It runs as UID/GID 10001,
with a read-only root, a 64 MB `/tmp` tmpfs, all Linux capabilities dropped and
`no-new-privileges`. A health check fetches `/conformance`. The smoke script
also executes the raster process, and the isolation checker inspects Docker's
actual runtime settings.

```bash
docker compose --file compose.release.yml up --build --detach
uv run python scripts/smoke_discovery.py --base-url http://localhost:5001
uv run python scripts/check_release_container.py
docker compose --file compose.release.yml exec -T api /venv/bin/python3 -c 'import terrio, pygeoapi; from terrio_processes.processes.info import TerrioInfoProcessor; print(terrio.__version__, pygeoapi.__version__)'
```

This is a local prototype, without authentication, persistent output storage,
TLS termination or production deployment automation. File-producing operations
will require an explicitly writable, bounded output location and HTTP delivery.
