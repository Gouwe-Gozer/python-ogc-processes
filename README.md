# Python OGC Processes

An extensible, standards-oriented OGC API – Processes application for integrating
and executing custom Python workflows, built on pygeoapi.

Wrap an importable Python function with pygeoapi's `BaseProcessor`, describe its
inputs/outputs and register it explicitly. The existing API and durable worker
handle discovery and execution. Start with [adding a Python process](docs/adding-a-process.md)
or run the [independent working example](examples/custom-process/README.md).
Integration requires a wrapper, runtime validation and deployment configuration;
Python functions are not exposed automatically.

The application is designed around OGC API – Processes Part 1: Core. The default
deployment runs one API with PostgreSQL and a separate worker. Ordinary requests
remain synchronous;
`Prefer: respond-async` submits a durable job with status and result endpoints.
List retained asynchronous jobs at `/jobs?f=json`; filter or page the list using
[Job List parameters](docs/asynchronous-execution.md#list-retained-jobs).
See [asynchronous execution](docs/asynchronous-execution.md).

The bundled Rasterio/GDAL operations demonstrate the processing interfaces with
**users' own GeoTIFFs**, supplied as controlled HTTPS references or inline base64.
Custom processes need not use Rasterio or accept raster data.

| Process | Purpose | Output |
| --- | --- | --- |
| `raster-info` | Inspect metadata, georeferencing and exact finite band statistics | JSON |
| `raster-warp` | Reproject a raster, retaining its width and height | GeoTIFF by value or download reference |
| `raster-sample-points` | Read one band at WGS84 GeoJSON point locations | GeoJSON by value or download reference |
| `raster-reclassify` | Map numeric ranges in one band to integer classes | GeoTIFF by value or download reference |
| `raster-polygonize` | Convert contiguous raster classes into WGS84 polygons | GeoJSON by value or download reference |

## Run the service

From the repository root, with Docker Compose installed:

```bash
docker compose --file compose.release.yml up --build --detach
```

Open <http://localhost:5001/processes?f=json> for available processes and
<http://localhost:5001/openapi> for interactive API documentation.
Stop the release with `docker compose --file compose.release.yml down`;
stored results and job data are retained in their named volumes.
Set both the published port and client-facing URL when using another address:

```bash
API_PORT=5002 PYGEOAPI_SERVER_URL=http://localhost:5002 docker compose --file compose.release.yml up --build --detach
```

The default API title is **Python Processing Service**. Set `PYGEOAPI_TITLE` and
`PYGEOAPI_DESCRIPTION` in the environment or `.env` to customize the displayed
metadata; see [service identity](docs/release-image.md#service-identity).
Result references use `PYGEOAPI_SERVER_URL`; choose an address clients can reach.
See [deployment](docs/release-image.md) for storage and operating settings,
or [development](docs/development.md) for the bind-mounted development stack.

Compose derives its project name from the checkout directory: a checkout named
`python-ogc-processes` uses that name. Existing deployments should retain their
project name when reusing stored jobs/results; see [migration](docs/release-image.md#repository-and-deployment-migration).
Plain `docker compose up --detach` selects the development configuration;
keep `--file compose.release.yml` for the self-contained release. Both start
`api`, `db` and `worker`, sharing the definitions in `compose.base.yml`.
The database has no published host port. Set `GEO_JOB_PASSWORD` to a persistent,
URL-safe password for hosted use; the built-in password is for local development.

For a lightweight API without PostgreSQL or a worker:

```bash
docker compose -f compose.yml -f compose.sync.yml up --build --detach
```

Use `-f compose.release.yml -f compose.sync.yml` for the self-contained equivalent.

## Process your raster

With the service running, install the local example client with Python 3.12 and
user-installed `uv`, then inspect and reproject the packaged sample GeoTIFF:

```bash
uv sync --locked --all-groups
mkdir -p runtime-data
uv run python scripts/process_raster.py \
  src/geo_processes/data/samples/AHN4_R5_117000_517000.TIF \
  --output runtime-data/ahn4-wgs84.tif \
  --target-crs EPSG:4326 --base-url http://localhost:5001
```

The command prints source dimensions/band count, submits the file inline and
downloads the reprojected GeoTIFF to `runtime-data/ahn4-wgs84.tif`. Replace the
input path to use your own raster. The destination's parent directory must exist;
choose another output filename when rerunning, since existing files are preserved.
Failed downloads are discarded. For a working GeoJSON point-sampling example,
see [use the samples for processing](docs/sample-data.md#use-the-samples-for-processing).

For a quick API check, submit the bundled fixture as ordinary inline data:

```bash
curl --fail-with-body http://localhost:5001/processes/raster-info/execution \
  -H 'Content-Type: application/json' \
  --data-binary @examples/info-request.json
```

This requests a document response: HTTP 200 JSON containing `info.value`.
See [input examples](docs/inputs.md) for HTTPS references and manual local-file
requests, and [result formats](docs/results.md#http-contract) for all warp modes.
See [operation contracts](docs/raster-operations.md)
for parameters, executable local-file examples and GeoJSON delivery.
For output-to-input reuse, see [raster chaining](docs/inputs.md#chain-raster-operations):
generated references need public HTTPS deployment to meet the input policy.

## Supported scope

Python processes share one installed dependency environment. The async worker
executes one job at a time, with a configurable timeout capped at **300 seconds**.
CPU/RAM can be changed in Compose; input helpers and file delivery have additional
application limits. Review [resource configuration](docs/release-image.md#resource-configuration)
before integrating a workload. Large ML workflows, isolated dependencies and
distributed execution are not demonstrated by the bundled examples.

Read-only [sample datasets](docs/sample-data.md) are available through
`/collections/sample-points/items?f=json`, `/collections/sample-polygons/items?f=json`
and `/sample-data/AHN4_R5_117000_517000.TIF`. The points and polygon are inside
the matching raster footprint. Feature data follows OGC API – Features conventions.

- GeoTIFF inputs: at most **16 MiB** and **1,048,576 samples**, including bands;
  execution JSON is limited to **24 MiB**. HTTPS inputs require public destinations
  and port 443. See [input policy](docs/inputs.md#limits-validation-and-cleanup).
- Warp targets: **EPSG:28992**, **EPSG:4326**, **EPSG:3857**. Resampling is
  **bilinear** by default, with **nearest** also available. Output dimensions
  match the source; resolution and extent controls are not exposed.
  CRS/resampling values also accept controlled HTTPS JSON/text references;
  see [scalar input forms](docs/inputs.md#scalar-input-references).
- Sampling accepts **Point**, **MultiPoint** or **Point FeatureCollection** inputs,
  up to **1,000 locations** in WGS84 longitude/latitude.
  Polygonize accepts an integer categorical band of at most **65,536 pixels**,
  producing at most **4,096 features / 16 MiB GeoJSON**. Reclassify accepts up to
  **128 non-overlapping ranges**; see [operation limits](docs/raster-operations.md).
- Omitted `response` means `raw`; omitted transmission means `value`.
  Info returns JSON; warp/reclassify return TIFF; sample/polygonize return GeoJSON.
  Explicit reference transmission provides a downloadable result.
- Stored results expire after **24 hours** by default. Capacity defaults to
  **64 MiB / 256 files**; busy/full processing returns 503. See [result lifecycle](docs/results.md).
- Dataset identifiers, server paths, reusable uploads and callbacks are unsupported.
  The synchronous-only opt-out does not retain jobs. There is no built-in
  authentication: job IDs/status metadata are discoverable through `/jobs`, and
  job results and file links are accessible without per-user authorization until
  expiry. Protect the API at deployment when processing private data.

Passing tests is not OGC certification. The advertised conformance classes and
remaining implementation gaps are documented in [validation](docs/validation.md).

## Documentation

- [Repeatable validation commands](docs/validation.md#repeatable-commands):
  `make test`, `make validate-geonovum`, `make validate` and `make validate-cite`.
- [Raster operation contracts](docs/raster-operations.md) and [JSON exceptions](docs/errors.md).
- [Resource configuration](docs/release-image.md#resource-configuration): deployment settings and hardcoded limits.
- [Development and checks](docs/development.md), [architecture](docs/architecture.md)
  and [adding a process](docs/adding-a-process.md), including the
  [independent Python example](examples/custom-process/README.md).
- [Release deployment](docs/release-image.md), [client interoperability](docs/validation.md#client-interoperability)
  and [future work](docs/roadmap.md).

## License and origins

Source: [Gouwe-Gozer/python-ogc-processes](https://github.com/Gouwe-Gozer/python-ogc-processes).

Maintained by **Minnert Wijnands (Gouwe-Gozer)** under the [MIT License](LICENSE).
This project reuses pygeoapi integration, testing and deployment infrastructure
from the MIT-licensed
[`bkn-terrain-processes`](https://github.com/Gouwe-Gozer/bkn-terrain-processes).
Original copyright and licence terms are preserved alongside this project's
copyright. See [third-party notices](THIRD_PARTY_NOTICES.md).
