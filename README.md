# geo-processes

A small OGC API – Processes service built on pygeoapi and Rasterio/GDAL.
**`raster-info`** inspects a GeoTIFF supplied by the user;
**`raster-warp`** reprojects it and delivers a GeoTIFF by value or download
reference. Both operations run synchronously. HTTPS inputs use a bounded
resolver; raster processing uses a validated local file.

**Submit your own raster** as an HTTPS reference or inline base64 GeoTIFF.
The examples submit a small bundled GeoTIFF as ordinary inline data. See
[user inputs](docs/inputs.md) for local-file requests, URL policy and limits,
and the [roadmap](docs/roadmap.md) for later service milestones.

## Run it

```bash
uv sync --locked --all-groups
docker compose up --build --detach
```

Open <http://localhost:5001/processes/raster-info?f=json> for the process
schema and <http://localhost:5001/openapi> for interactive API documentation.
If port 5001 is occupied, set both variables when starting Compose:

```bash
API_PORT=5002 PYGEOAPI_SERVER_URL=http://localhost:5002 docker compose up --build --detach
```

Process your local GeoTIFF and save a reprojected copy:

```bash
uv run python scripts/process_raster.py my-dem.tif --output my-dem-wgs84.tif \
  --target-crs EPSG:4326 --base-url http://localhost:5001
```

The command prints source dimensions/band count, submits the raster inline,
requests a download reference and saves the returned GeoTIFF. It preserves
existing destination files and removes partial downloads. The input must fit
the [service limits](docs/inputs.md#limits-validation-and-cleanup). See
[local-file usage](docs/inputs.md#process-a-local-file) for options and a bundled example.

Inspect the small demo file through the same input contract as your own rasters:

```bash
curl --fail-with-body http://localhost:5001/processes/raster-info/execution \
  -H 'Content-Type: application/json' \
  --data-binary @examples/info-request.json
```

HTTP 200, `application/json`: `{"info":{"value":{...raster information...}}}`.
The example requests a document response. Its `info.value` includes
`"size": [4, 3]`, `"band_count": 1`, EPSG:28992 and band statistics with
minimum 1, maximum 12, mean 6.5 and 12 valid cells.

Omitting `response` defaults to `raw`, returning the raster information directly.
The output identifier is `info`. Omitting `outputs` selects it; omitting
`transmissionMode` selects `value`. `Prefer: respond-async` still returns a
synchronous 200 with no job URL. Invalid inputs or unsupported options return
JSON 400 errors; internal processing failures return a sanitized 500.
JSON errors include a stable `type` URI and retain legacy `code`/`description`;
see the [exception catalogue](docs/errors.md).

## Reproject a raster

To use your own HTTPS-hosted raster, replace the example's `source` value with
`{"href":"https://data.example.org/my-dem.tif","type":"image/tiff"}` in the
examples below. For a local file, use the [inline submission example](docs/inputs.md#submit-a-local-file-inline).

Choose a target CRS from **EPSG:28992**, **EPSG:4326** or **EPSG:3857**.
Resampling is **bilinear** by default; **nearest** is also supported. The target
grid retains the source width and height, with pixel size determined by the
transformed extent. The example file has four columns and three rows.

The default raw/value response is an actual GeoTIFF:

```bash
curl --fail-with-body http://localhost:5001/processes/raster-warp/execution \
  -H 'Content-Type: application/json' \
  --data-binary @examples/warp-value-request.json \
  --output warped.tif
```

For a downloadable reference, explicitly request reference transmission:

```bash
curl --fail-with-body http://localhost:5001/processes/raster-warp/execution \
  -H 'Content-Type: application/json' \
  --data-binary @examples/warp-reference-request.json
```

HTTP 200, `application/json` (the identifier varies):

```json
{"result":{"href":"http://localhost:5001/results/0123456789abcdef0123456789abcdef/output.tif","type":"image/tiff"}}
```

GET the returned `href` to download the GeoTIFF. Configure `PYGEOAPI_SERVER_URL`
to the address your clients can reach; generated URLs use that canonical address.
Startup validates the URL, storage and operating limits before serving requests
and prints the effective configuration; see [startup validation](docs/development.md#startup-validation).

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

`source` accepts a controlled HTTPS reference, inline base64 string or qualified
inline base64 GeoTIFF. Dataset identifiers such as `demo-dem` are not API inputs.
Inputs are limited to 16 MiB and 1,048,576 samples including bands;
JSON requests to 24 MiB. Paths, raw URL strings, callbacks and async jobs are
unsupported. HTTPS destinations must resolve exclusively to public addresses.
`raster-info` still offers only JSON value transmission; `raster-warp` also
offers GeoTIFF references. User inputs are removed after execution independently
of output retention; see [input lifecycle](docs/inputs.md#limits-validation-and-cleanup).

The adapter has no pygeoapi dependency. Each operation owns its process
metadata, input validation and result representation. Shared request/manager
code does not assume every future operation returns one JSON output.

Pinned versions: **pygeoapi 0.24.0**, **Rasterio 1.4.3**, **NumPy 1.26.4**,
Python **3.12**. These application versions match the Docker environment.
The image and local Rasterio wheels can bundle different GDAL versions; both
are validated. See the [metadata contract](docs/raster-info.md).

This project was previously named `terrio-processes`. The
[pivot decision](docs/rasterio-pivot.md) records the backend and naming change,
including breaking API/configuration changes and preserving existing volumes.
The GitHub repository retains its existing name until its owner renames it.

See [development commands](docs/development.md), [architecture](docs/architecture.md),
[adding a process](docs/adding-a-process.md),
[OGC review guidance and validation limits](docs/validation.md),
[client interoperability log](docs/client-interoperability.md),
[release deployment](docs/release-image.md),
[warp milestone](docs/warp-milestone.md)
and the [historical migration report](docs/migration.md). Passing local tests is not OGC
certification. Additional operations, reusable uploads and deployment work remain
in the [roadmap](docs/roadmap.md).

## License and origins

Maintained by **Minnert Wijnands (Gouwe-Gozer)** and licensed under the
[MIT License](LICENSE).

`geo-processes` derives reusable pygeoapi integration, testing and deployment
infrastructure from the MIT-licensed
[`bkn-terrain-processes`](https://github.com/Gouwe-Gozer/bkn-terrain-processes)
project. The original copyright and MIT terms are preserved alongside the
copyright for this project's changes. See [third-party notices](THIRD_PARTY_NOTICES.md)
for attribution and dependency licences.
