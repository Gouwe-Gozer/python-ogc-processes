# Architecture

The official pygeoapi package supplies discovery, configuration, Flask routes
and process registration. `terrio_processes.processes.info.TerrioInfoProcessor`
validates the `source` identifier and output options, then calls the plain
Python adapter in `engine.py`. The adapter directly invokes
`terrio.info(path, stats=True)`; no CLI, shell or secondary backend is involved.

`contracts/info.py` describes the bounded operation and its JSON schemas. The
GeoTIFF ships inside the Python package. `demo-dem` resolves through a fixed
operator-owned registry; a client never controls a filesystem path or URL.
The raster is Float32, one band, four columns by three rows, EPSG:28992,
10-metre pixels, nodata -9999, with values 1 through 12 in row-major order.
Its origin is (155000, 463000). Tests verify its actual Terrio output.

`OgcSynchronousManager` retains pygeoapi's registration and synchronous manager
interface. Each processor owns its optional `format_result` method, so shared
code passes through native values and media types and delegates document
encoding. The manager preserves typed client/server exceptions and sanitizes
unexpected failures. It does not implement output storage, async jobs,
reference transmission or multipart responses.

The registered execution routes have a small Flask boundary guard because
pygeoapi 0.24.0 still dereferences malformed execute documents without checking
all JSON shapes. It also rejects unimplemented callback and execution members.
The process validates its own inputs and output options, including when called
directly without HTTP.

The application OpenAPI generator keeps upstream discovery paths and metadata,
corrects wrong discovery schemas and missing limits/404s, and asks each process
for its execution contract. It rejects untested pygeoapi upgrades. The container
uses a short owned entrypoint; no upstream source or shell script is edited.

Before adding `terrio-warp`, choose bounded result storage, an external HTTP
retrieval URL, retention/cleanup, resource limits, and the supported transmission
modes. A document/reference result must contain a retrievable `href` and media
type under the output identifier. Raw/reference, if offered, requires an empty
204 response with `Link` headers. Binary value results need their declared
media type. Input `href` support needs a separate safe fetch/validation design.
