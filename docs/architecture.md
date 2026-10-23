# Architecture

The following describes the current Terrio runtime. The approved
[Rasterio pivot](rasterio-pivot.md) replaces its raster adapter and project/process
names while preserving the OGC, result-storage and deployment boundaries.

The official pygeoapi package supplies discovery, configuration, Flask routes
and process registration. `TerrioInfoProcessor` and `TerrioWarpProcessor`
validate each operation's inputs and output options, then call the plain
Python adapter in `engine.py`. It invokes `terrio.info` and `terrio.warp`
directly; no CLI, shell or secondary backend is involved.

`contracts/info.py` and `contracts/warp.py` describe the independent operations.
`datasets.py` is their shared operator-owned input registry. The
GeoTIFF ships inside the Python package. `demo-dem` resolves through a fixed
operator-owned registry; a client never controls a filesystem path or URL.
The raster is Float32, one band, four columns by three rows, EPSG:28992,
10-metre pixels, nodata -9999, with values 1 through 12 in row-major order.
Its origin is (155000, 463000). Tests verify its actual Terrio output.

`OgcSynchronousManager` retains pygeoapi's registration and synchronous manager
interface. Each processor owns its optional `format_result` method, so shared
code passes through native values and media types and delegates document
encoding. The manager preserves typed client/server exceptions and sanitizes
unexpected failures. A processor can return a `ProcessResponse` to select its
media type, headers and HTTP representation. The Flask boundary removes a
private status marker to correct pygeoapi 0.24.0's fixed successful HTTP 200 to
204 for raw/reference execution. This is covered by actual HTTP tests; the
marker is never sent to clients. The manager assumes no particular output IDs
or count, and does not implement storage, async jobs or multipart responses.

The registered execution routes have a small Flask boundary guard because
pygeoapi 0.24.0 still dereferences malformed execute documents without checking
all JSON shapes. It also rejects unimplemented callback and execution members.
The process validates its own inputs and output options, including when called
directly without HTTP.

The application OpenAPI generator keeps upstream discovery paths and metadata,
corrects wrong discovery schemas and missing limits/404s, and asks each process
for its execution contract. It rejects untested pygeoapi upgrades. The container
uses a short owned entrypoint; no upstream source or shell script is edited.

`storage.py` handles bounded local outputs independently of OGC jobs. It writes
each raster in a private workspace, atomically publishes a UUID-named file and
serializes writers with a Linux file lock. The result route only reads regular,
unexpired files and refuses symlinks and invalid identifiers. Download URLs use
the configured canonical API base URL. Storage and lifecycle details are in
[results.md](results.md).

Warp output dimensions are pinned to the source grid to bound allocation;
resolution follows the reprojected extent. Clients select only an approved
dataset, one of three target CRSs and nearest/bilinear resampling. Enlarging the
input catalogue requires operator review and tests. External input `href`
support needs a separate safe fetch/validation design.

The target service processes users' own rasters. The fixed registry is the
prototype input boundary; a larger hosted catalogue is optional. The
[roadmap](roadmap.md) puts a user-submission flow before a large process
catalogue. Its proposed input resolver should be separate from OGC processors
and the Terrio adapter, with input cleanup independent of output retention.
Any shared raster-response helper should preserve per-operation contracts and
the existing response/transmission combinations. See the
[OGC review guide](validation.md#ogc-review-guide) before changing these contracts.
