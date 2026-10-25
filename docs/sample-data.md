# Public sample data

The release image includes two small read-only OGC API – Features collections
and their matching GeoTIFF. No host data mount is needed. Development uses the
same files through the existing source mount. Rebuild the image after changing
sample data.

| Resource | Local URL |
| --- | --- |
| Collection catalogue | <http://localhost:5001/collections?f=json> |
| Three sample points | <http://localhost:5001/collections/sample-points/items?f=json> |
| Point by stable ID | <http://localhost:5001/collections/sample-points/items/point-1?f=json> |
| Sample polygon | <http://localhost:5001/collections/sample-polygons/items?f=json> |
| Polygon by stable ID | <http://localhost:5001/collections/sample-polygons/items/polygon-1?f=json> |
| Matching GeoTIFF | <http://localhost:5001/sample-data/AHN4_R5_117000_517000.TIF> |

Collection metadata is at `/collections/sample-points` and
`/collections/sample-polygons`, with `items` links and a related GeoTIFF link.
Use `f=html` for browser previews. URLs follow the configured public API URL,
including any path prefix.

## Geometry and raster alignment

Points preserve the supplied longitude/latitude coordinates and empty
properties, adding stable top-level IDs `point-1` through `point-3`:

- `[4.836065, 52.647618]`
- `[4.827911, 52.645173]`
- `[4.834395, 52.644807]`

`polygon-1` surrounds those points with approximately **40 m padding** in the
raster's native coordinate system. It is contained within the raster footprint
and is published in WGS84 longitude/latitude. Tests verify all three points
are inside the polygon and fall on valid raster pixels.

The GeoTIFF is copied unchanged from the user-supplied
`~/projects/AHN4_R5_117000_517000.TIF`:

| Property | Value |
| --- | --- |
| Size | 200 × 200 pixels, one float32 band |
| Grid | 5 m pixels |
| CRS | EPSG:7415 (RD New + NAP) |
| Bounds in native CRS | `[117000, 517000, 118000, 518000]` |
| Nodata | `-9999` |
| File size | 139,824 bytes |
| SHA-256 | `7401de276a5f08f9fe3b6003d0860159e4544c348d0747f01a865a5dcdcf7f33` |

No source raster bytes or coordinates are rewritten. The polygon is generated
for these sample locations. Packaged files live in
`src/geo_processes/data/samples/`. These public sample files have stable URLs;
generated [process results](results.md) retain their separate expiry/quota policy.

## Features conventions

pygeoapi's built-in **GeoJSON provider** supplies collection metadata, individual
items, paging and bbox queries. Responses use `application/geo+json`, stable
feature IDs, links, `timeStamp`, `numberMatched` and `numberReturned`.

Examples:

```text
/collections/sample-points/items?f=json&limit=1
/collections/sample-points/items?f=json&bbox=4.835,52.647,4.837,52.649
```

Follow the returned `next` link for paging. Data edits and CQL filtering are
unsupported. CQL requests return a clear HTTP 400 instead of silently returning
unfiltered data; use bbox or individual feature IDs. The generated OpenAPI omits
the unsupported CQL query POSTs, and `/conformance` omits the inherited CRUD and
CQL2 claims for these providers. Integration
tests validate responses against an unchanged offline snapshot of the
[official Features schemas](https://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/schemas/).
This is evidence for the sample routes, not a new conformance certification.

The empty feature properties are intentional. A targeted OpenAPI correction
omits the optional property-selection parameter when upstream would emit an
invalid empty enum. The existing response hook assigns the GeoJSON media type
to successful feature item responses; discovery and errors remain ordinary JSON.

## Use the samples for processing

Clients can download the TIFF and submit its bytes as qualified base64. The
point Features response can be passed directly as `inputs.points.value`;
collection-level metadata is accepted and ignored during sampling.

The input resolver still requires **public HTTPS** references. A local
`http://localhost:5001/...` URL is suitable for client-side downloads, but is not
a permitted server-side input reference. This local example uses inline values:

```bash
uv run python - <<'PY'
import base64
import json
from urllib.request import Request, urlopen

base = "http://localhost:5001"
with urlopen(base + "/collections/sample-points/items?f=json") as response:
    points = json.load(response)
with urlopen(base + "/sample-data/AHN4_R5_117000_517000.TIF") as response:
    raster = response.read()
payload = {"inputs": {
    "source": {"value": base64.b64encode(raster).decode("ascii"),
               "mediaType": "image/tiff", "encoding": "base64"},
    "points": {"value": points, "mediaType": "application/geo+json"},
}}
request = Request(base + "/processes/raster-sample-points/execution",
                  data=json.dumps(payload).encode(),
                  headers={"Content-Type": "application/json"})
with urlopen(request) as response:
    print(response.read().decode())
PY
```

The sampled values are approximately **1.9285**, **3.2804** and **-2.1011** in
point order. Keep client rendering observations in the
[interoperability log](client-interoperability.md).

For local commands, data paths default relative to the repository root. The
image sets `GEO_SAMPLE_DATA_DIR` to its packaged sample directory. An operator
override must point both the feature providers and static file serving at a
directory containing only data intended for public access.
