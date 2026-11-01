# Python OGC Processes

An extensible, standards-oriented OGC API – Processes application for integrating
and executing custom Python workflows, built on pygeoapi.

The service provides process discovery, synchronous and durable asynchronous
execution, job tracking and result retrieval.

## Quick start

With Docker and Docker Compose installed, run from the repository root:

```bash
docker compose --file compose.release.yml up --build --detach
```

This starts the API, PostgreSQL and a separate worker. Open
<http://localhost:5001/processes?f=json> to discover processes and
<http://localhost:5001/openapi> for interactive API documentation.

Execute an included example with its packaged input:

```bash
curl --fail-with-body http://localhost:5001/processes/raster-info/execution \
  -H 'Content-Type: application/json' \
  --data-binary @examples/info-request.json
```

The response is HTTP 200 JSON containing `info.value`.
To stop the service, run `docker compose --file compose.release.yml down`;
job data and stored results remain in their named volumes.

## Adding a Python process

To add a process, wrap your Python function with pygeoapi's `BaseProcessor`,
define its inputs and outputs, and register it in the service configuration.
Keep the function in this repository or install an external Python package;
both the API and worker need the same code and dependencies.

Follow [adding a Python process](docs/adding-a-process.md) or run the
[working custom-process example](examples/custom-process/README.md).

**Using a coding agent?** The repository includes [AGENTS.md](AGENTS.md) with
an integration checklist and links to development, deployment and testing guidance.
Provide your Python script and ask your agent to integrate it, including tests
and deployment configuration.

## Included processes

The bundled Rasterio/GDAL operations are example processors. They accept
GeoTIFFs through controlled HTTPS references or inline base64. Custom Python
processes need not use Rasterio or accept raster data.

| Process | Purpose | Output |
| --- | --- | --- |
| `raster-info` | Inspect metadata, georeferencing and band statistics | JSON |
| `raster-warp` | Reproject a raster | GeoTIFF |
| `raster-sample-points` | Sample a band at GeoJSON point locations | GeoJSON |
| `raster-reclassify` | Map numeric ranges to integer classes | GeoTIFF |
| `raster-polygonize` | Convert raster classes to polygons | GeoJSON |

See [raster operation contracts](docs/raster-operations.md) for parameters and
limits, [processing your own rasters](docs/inputs.md) for local-file and HTTPS
requests, and [sample data](docs/sample-data.md#use-the-samples-for-processing)
for GeoTIFF and point-sampling walkthroughs.

## Deployment considerations

- Use `compose.release.yml` for the self-contained deployment. Plain
  `docker compose up` selects the bind-mounted development stack.
  A [synchronous-only opt-out](docs/asynchronous-execution.md#start) is available.
- Set `PYGEOAPI_SERVER_URL` to the client-facing address so generated links are
  reachable. The default API title is **Python Processing Service**; title and
  description are configurable. See [deployment settings](docs/release-image.md).
- Processes share one dependency environment. The async worker runs one job at
  a time, with a configurable timeout capped at **300 seconds**. Review
  [resource settings and application limits](docs/release-image.md#resource-configuration)
  before integrating a workload.
- Stored results expire after **24 hours** by default, and storage is bounded.
  Keep the same Compose project name when reusing existing volumes;
  see [result lifecycle](docs/results.md) and [deployment migration](docs/release-image.md#repository-and-deployment-migration).
- There is no built-in authentication or per-user authorization. Protect private
  job data and results. TLS, credentials, backups and monitoring are deployment
  responsibilities; see [security](SECURITY.md).

The application targets OGC API – Processes Part 1: Core. Advertised capabilities
and known validation limitations are documented in [validation](docs/validation.md).
Passing tests does not establish formal OGC certification.

## Documentation

- [Adding a Python process](docs/adding-a-process.md) and [contributing](CONTRIBUTING.md).
- [Development and checks](docs/development.md) and [architecture](docs/architecture.md).
- [Release deployment and configuration](docs/release-image.md).
- [Asynchronous execution and job listing](docs/asynchronous-execution.md).
- [Raster inputs](docs/inputs.md), [operation contracts](docs/raster-operations.md),
  [results](docs/results.md) and [sample data](docs/sample-data.md).
- [JSON exceptions](docs/errors.md), [standards validation and client interoperability](docs/validation.md)
  and [roadmap](docs/roadmap.md).

## License and attribution

Source: [Gouwe-Gozer/python-ogc-processes](https://github.com/Gouwe-Gozer/python-ogc-processes).

Maintained by **Minnert Wijnands (Gouwe-Gozer)** under the [MIT License](LICENSE).
This project reuses pygeoapi integration, testing and deployment infrastructure
from the MIT-licensed
[`bkn-terrain-processes`](https://github.com/ITBreinstein/bkn-terrain-processes).
Original copyright and licence terms are preserved alongside this project's
copyright. See [third-party notices](THIRD_PARTY_NOTICES.md).
