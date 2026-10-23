# Terrio Processes

A small OGC API – Processes service built on pygeoapi and Terrio's Rust-backed
Python binding. The first process, **`terrio-info`**, inspects a bundled GeoTIFF
and returns metadata, georeferencing and exact band statistics. It runs offline
and synchronously.

## Run it

```bash
uv sync --locked --all-groups
docker compose up --build --detach
```

Open <http://localhost:5001/processes/terrio-info?f=json> for the process
schema and <http://localhost:5001/openapi> for interactive API documentation.
If port 5001 is occupied, set both variables when starting Compose:

```bash
API_PORT=5002 PYGEOAPI_SERVER_URL=http://localhost:5002 docker compose up --build --detach
```

Inspect the demo raster (omitted `response` defaults to `raw`):

```bash
curl --fail-with-body http://localhost:5001/processes/terrio-info/execution \
  -H 'Content-Type: application/json' \
  --data '{"inputs":{"source":"demo-dem"}}'
```

HTTP 200, `application/json`: the native Terrio dictionary, including
`"size": [4, 3]`, `"band_count": 1`, EPSG:28992 and band statistics with
minimum 1, maximum 12, mean 6.5 and 12 valid cells.

Request an OGC results document:

```bash
curl --fail-with-body http://localhost:5001/processes/terrio-info/execution \
  -H 'Content-Type: application/json' \
  --data '{"inputs":{"source":"demo-dem"},"outputs":{"info":{"transmissionMode":"value"}},"response":"document"}'
```

HTTP 200, `application/json`: `{"info":{"value":{...raster information...}}}`.
The output identifier is `info`. Omitting `outputs` selects it; omitting
`transmissionMode` selects `value`. `Prefer: respond-async` still returns a
synchronous 200 with no job URL. Invalid inputs or unsupported options return
JSON 400 errors; an unavailable configured dataset returns a sanitized 500.

## Scope

`source` is an inline string from the published dataset enum. Currently only
`demo-dem` is accepted, mapped to a read-only, bundled 352-byte GeoTIFF.
Paths, URLs, OGC input references, callbacks, async jobs, file downloads and
reference output transmission are outside this milestone. No runtime request
contacts a remote data service.

The adapter has no pygeoapi dependency. Each operation owns its process
metadata, input validation and result representation. Shared request/manager
code does not assume every future operation returns one JSON output.

Pinned versions: **pygeoapi 0.24.0**, **Terrio 0.4.2**, Python **3.12**.
Both run in the same interpreter in the Docker image. This project derives
reusable infrastructure from BKN; required notices remain in [LICENSE](LICENSE)
and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

See [development commands](docs/development.md), [architecture](docs/architecture.md),
[validation limits](docs/validation.md), [release deployment](docs/release-image.md)
and the [migration report](docs/migration.md). Passing local tests is not OGC
certification. The next milestone is `terrio-warp`, after deciding how to serve
and expire downloadable results.
