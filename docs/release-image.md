# Release deployment

`compose.release.yml` builds a self-contained image with application source,
canonical configuration and licence notices. Its official pygeoapi 0.24.0 base
is pinned by manifest digest in `docker/Dockerfile`. Rasterio and NumPy are
explicitly installed into the same `/venv` used by Gunicorn; application pins
are listed in [development](development.md). Transitive dependencies and bundled
GDAL/PROJ resources may differ from the local uv environment.

## Run and inspect

```bash
docker compose --file compose.release.yml up --build --detach
uv run python scripts/check_release_container.py
docker compose --file compose.release.yml exec -T api /venv/bin/python3 -c 'import rasterio, numpy, pygeoapi; print(rasterio.__version__, rasterio.__gdal_version__, numpy.__version__, pygeoapi.__version__)'
```

The isolation checker needs the local [development environment](development.md).
Run the [container smoke checks](development.md#container-and-integration-checks)
to verify discovery, actual processing, all result modes and restart persistence.
A health check alone only fetches `/conformance`.

## Startup and public URL

The owned entrypoint validates runtime settings and prints the effective public
URL, process IDs, input policy and result limits. It then generates OpenAPI in
`/tmp` and starts two synchronous Gunicorn workers, with a 30-second timeout,
on internal port 8080. Directory probes do not delete stored results.
See [startup validation](development.md#startup-validation) for exact checks.

Compose publishes port 5001 by default. Set `API_PORT` and `PYGEOAPI_SERVER_URL`
together when changing the external address, as shown in the [README](../README.md).
Generated links use that canonical URL, including any proxy prefix, rather than
the requesting Host header. URL validation does not test client reachability.

`WSGI_WORKERS`, `WSGI_WORKER_TIMEOUT` and `CONTAINER_PORT` are container environment
settings. Supply overrides through an explicit Compose override or another
container launcher; these variables are not forwarded from the host by the
supplied Compose files. A bind-port override also needs matching port mapping
and health-check configuration.

## Isolation and storage

Release Compose sets:

- UID/GID `10001:10001`, read-only root, dropped capabilities and `no-new-privileges`;
- a 64 MiB `/tmp` tmpfs with `noexec,nosuid`, including private input workspaces;
- one writable named volume, `results`, mounted at `/var/lib/geo/results`;
- 512 MiB memory, one CPU and 128 processes.

The image initializes result-directory ownership before dropping privileges.
No source/configuration bind mounts or runtime root initialization are required.
These Compose restrictions do not apply automatically to the development stack
or to an image launched with other options.

The [input policy](inputs.md) covers HTTPS restrictions, decoding and cleanup.
The [result guide](results.md) owns retention, capacity, locking and maintenance
settings. Result links are accessible to anyone who knows them until expiry.

A normal `docker compose --file compose.release.yml down` retains the result
volume; adding `--volumes` deletes it. Keep the same Compose project name when
renaming a checkout or upgrading an existing installation, so Docker reuses the
same volume. The current project is `raster-processes`, with result volume
`raster-processes_results`. See [local reset instructions](development.md#container-and-integration-checks)
when those disposable results should be discarded deliberately.

Authentication, TLS termination, hosting, monitoring and access/egress policy
remain deployment responsibilities; this repository supplies a bounded service
and release artifact rather than managed production operations.
