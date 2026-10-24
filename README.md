# geo-processes

A small OGC API – Processes service for **users' own GeoTIFFs**, built on
pygeoapi and Rasterio/GDAL. Submit a raster as an HTTPS reference or inline
base64 and receive information or a reprojected file. Execution is synchronous.

| Process | Purpose | Output |
| --- | --- | --- |
| `raster-info` | Inspect metadata, georeferencing and exact finite band statistics | JSON |
| `raster-warp` | Reproject a raster, retaining its width and height | GeoTIFF by value or download reference |

## Run the service

From the repository root, with Docker Compose installed:

```bash
docker compose --file compose.release.yml up --build --detach
```

Open <http://localhost:5001/processes?f=json> for available processes and
<http://localhost:5001/openapi> for interactive API documentation.
Set both the published port and client-facing URL when using another address:

```bash
API_PORT=5002 PYGEOAPI_SERVER_URL=http://localhost:5002 docker compose --file compose.release.yml up --build --detach
```

Result references use `PYGEOAPI_SERVER_URL`; choose an address clients can reach.
See [deployment](docs/release-image.md) for storage and operating settings,
or [development](docs/development.md) for the bind-mounted development stack.

## Process your raster

Install the local example client with Python 3.12 and user-installed `uv`, then
inspect, reproject and save a GeoTIFF:

```bash
uv sync --locked --all-groups
uv run python scripts/process_raster.py my-dem.tif --output my-dem-wgs84.tif \
  --target-crs EPSG:4326 --base-url http://localhost:5001
```

The command prints source dimensions/band count, submits the file inline and
saves the downloaded result. The destination's parent directory must exist;
existing files are preserved and failed downloads are discarded.

For a quick API check, submit the bundled fixture as ordinary inline data:

```bash
curl --fail-with-body http://localhost:5001/processes/raster-info/execution \
  -H 'Content-Type: application/json' \
  --data-binary @examples/info-request.json
```

This requests a document response: HTTP 200 JSON containing `info.value`.
See [input examples](docs/inputs.md) for HTTPS references and manual local-file
requests, and [result formats](docs/results.md#http-contract) for all warp modes.

## Supported scope

- GeoTIFF inputs: at most **16 MiB** and **1,048,576 samples**, including bands;
  execution JSON is limited to **24 MiB**. HTTPS inputs require public destinations
  and port 443. See [input policy](docs/inputs.md#limits-validation-and-cleanup).
- Warp targets: **EPSG:28992**, **EPSG:4326**, **EPSG:3857**. Resampling is
  **bilinear** by default, with **nearest** also available. Output dimensions
  match the source; resolution and extent controls are not exposed.
  CRS/resampling values also accept controlled HTTPS JSON/text references;
  see [scalar input forms](docs/inputs.md#scalar-input-references).
- Omitted `response` means `raw`; omitted transmission means `value`.
  `raster-info` returns JSON; `raster-warp` returns native TIFF bytes by default.
  Explicit reference transmission provides a downloadable result.
- Stored results expire after **24 hours** by default. Capacity defaults to
  **64 MiB / 256 files**; busy/full processing returns 503. See [result lifecycle](docs/results.md).
- Dataset identifiers, server paths, reusable uploads, callbacks and async jobs
  are unsupported. The service has no built-in authentication; result links are
  accessible to anyone who knows them until expiry.

Passing tests is not OGC certification. The advertised conformance classes and
remaining implementation gaps are documented in [validation](docs/validation.md).

## Documentation

- [Raster metadata](docs/raster-info.md) and [JSON exceptions](docs/errors.md).
- [Development and checks](docs/development.md), [architecture](docs/architecture.md)
  and [adding a process](docs/adding-a-process.md).
- [Release deployment](docs/release-image.md), [client interoperability](docs/client-interoperability.md)
  and [future work](docs/roadmap.md).

## License and origins

Maintained by **Minnert Wijnands (Gouwe-Gozer)** under the [MIT License](LICENSE).
This project reuses pygeoapi integration, testing and deployment infrastructure
from the MIT-licensed
[`bkn-terrain-processes`](https://github.com/Gouwe-Gozer/bkn-terrain-processes).
Original copyright and licence terms are preserved alongside this project's
copyright. See [third-party notices](THIRD_PARTY_NOTICES.md).
