# terrio-processes

A small OGC API – Processes service built on pygeoapi and Terrio's Rust-backed
Python binding. **`terrio-info`** inspects an approved local GeoTIFF;
**`terrio-warp`** reprojects it and delivers a GeoTIFF by value or download
reference. Both operations run offline and synchronously.

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

## Reproject a raster

Choose a target CRS from **EPSG:28992**, **EPSG:4326** or **EPSG:3857**.
Resampling is **bilinear** by default; **nearest** is also supported. The target
grid retains the source width and height, with pixel size determined by the
transformed extent. For `demo-dem`, the output remains four columns by three rows.

The default raw/value response is an actual GeoTIFF:

```bash
curl --fail-with-body http://localhost:5001/processes/terrio-warp/execution \
  -H 'Content-Type: application/json' \
  --data '{"inputs":{"source":"demo-dem","target_crs":"EPSG:4326"}}' \
  --output warped.tif
```

For a downloadable reference, explicitly request reference transmission:

```bash
curl --fail-with-body http://localhost:5001/processes/terrio-warp/execution \
  -H 'Content-Type: application/json' \
  --data '{"inputs":{"source":"demo-dem","target_crs":"EPSG:4326","resampling":"nearest"},"outputs":{"result":{"transmissionMode":"reference"}},"response":"document"}'
```

HTTP 200, `application/json` (the identifier varies):

```json
{"result":{"href":"http://localhost:5001/results/0123456789abcdef0123456789abcdef/output.tif","type":"image/tiff"}}
```

GET the returned `href` to download the GeoTIFF. Configure `PYGEOAPI_SERVER_URL`
to the address your clients can reach; generated URLs use that canonical address.

| Response | Transmission | HTTP result |
| --- | --- | --- |
| `raw` (default) | `value` (default) | 200, `image/tiff`, native GeoTIFF bytes |
| `document` | `value` | 200, JSON `result` containing `value` (base64), `encoding` and `mediaType` |
| `document` | `reference` | 200, JSON `result` containing `href` and `type` |
| `raw` | `reference` | 204, empty body, `Link` header pointing to the GeoTIFF |

Results persist in a Docker named volume and expire after **24 hours** by
default. Downloads then return JSON 404. Capacity is bounded to **64 MiB** and
**256 results**; a full store or concurrent warp returns a controlled JSON 503.
Existing unexpired files are retained. See [result storage](docs/results.md)
for configuration, cleanup and limits.

## Scope

`source` is an inline string from the published dataset enum. Currently only
`demo-dem` is accepted, mapped to a read-only, bundled 352-byte GeoTIFF.
Paths, URLs, OGC input references, callbacks and async jobs are not accepted.
`terrio-info` still offers only JSON value transmission; `terrio-warp` also
offers GeoTIFF references. No runtime request contacts a remote data service.

The adapter has no pygeoapi dependency. Each operation owns its process
metadata, input validation and result representation. Shared request/manager
code does not assume every future operation returns one JSON output.

Pinned versions: **pygeoapi 0.24.0**, **Terrio 0.4.2**, Python **3.12**.
Both dependencies run in the same interpreter in the Docker image.

See [development commands](docs/development.md), [architecture](docs/architecture.md),
[validation limits](docs/validation.md), [release deployment](docs/release-image.md),
[warp milestone](docs/warp-milestone.md)
and the [historical migration report](docs/migration.md). Passing local tests is not OGC
certification. Additional operations and remote inputs remain future milestones.

## License and origins

Maintained by **Minnert Wijnands (Gouwe-Gozer)** and licensed under the
[MIT License](LICENSE).

`terrio-processes` derives reusable pygeoapi integration, testing and deployment
infrastructure from the MIT-licensed
[`bkn-terrain-processes`](https://github.com/Gouwe-Gozer/bkn-terrain-processes)
project. The original copyright and MIT terms are preserved alongside the
copyright for this project's changes. See [third-party notices](THIRD_PARTY_NOTICES.md)
for attribution and dependency licences.
