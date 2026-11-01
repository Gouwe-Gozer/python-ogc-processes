# Raster operation contracts

All five processes support synchronous and durable asynchronous execution. They
reuse the [GeoTIFF input policy](inputs.md), pygeoapi registration and
[result lifecycle](results.md). Information has one `info` output; the other
operations have one `result` output. For sampling, reclassification and polygonization, `band` is a one-based
integer, default **1**. Unsupported inputs, formats,
bands or operation limits return an OGC exception with HTTP 400; input byte
limits return 413, unavailable capacity 503 and internal failures sanitized 500.

## Raster information — `raster-info`

`raster-info` returns application-defined JSON backed by Rasterio/GDAL and
NumPy. It does not expose a library's native metadata dictionary. The executable
schema is [contracts/info.py](../src/geo_processes/contracts/info.py).

The test fixture at `src/geo_processes/data/demo-dem.tif` is a one-band Float32,
4 by 3 GeoTIFF in EPSG:28992 with 10-metre pixels, origin (155000, 463000), nodata
-9999 and row-major values 1 through 12. Tests and examples submit its bytes
through the ordinary user-input contract; its filename is not an API identifier.

| Field | Meaning |
| --- | --- |
| `type`, `driver` | `raster` and `GTiff`, the supported input driver |
| `size`, `band_count` | Width/height in pixels and number of bands |
| `geo_transform` | Six coefficients in GDAL order: origin X, pixel X, rotation X, origin Y, rotation Y, pixel Y |
| `crs` | Object containing `epsg` and `wkt`, or null if no CRS is present; `epsg` can be null for a custom CRS |
| `extent` | `[left, bottom, right, top]` in source coordinates |
| `wgs84_extent` | Densified transformed bounds in longitude/latitude, or null without a CRS |
| `bands` | One object per band, with 1-based index, Rasterio/NumPy dtype name, nodata and statistics |
| `metadata` | Default-namespace dataset tags as a string-to-string object |

Nodata is a JSON number when finite, null when unset, or the string `NaN`,
`Infinity` or `-Infinity` for those non-finite nodata markers. Statistics exclude
masked/nodata pixels and all NaN/infinite samples. `valid_count` counts the
remaining finite samples. `min`, `max`, `mean` and population `std_dev` are
numbers, or null when no samples remain. JSON never contains non-standard
numeric NaN or infinity tokens. Complex rasters are unsupported.

All five raster operations enforce 16 MiB per input and 1,048,576 samples
including bands. Info reads one band at a time for exact statistics. It can
inspect a raster without a CRS; warp rejects that raster. All five accept
[user GeoTIFFs](inputs.md) through HTTPS references or inline base64. Source files are validated
and staged privately; metadata and all statistics refer to the supplied file.

Raw execution returns this object directly. Document execution returns
`{"info":{"value":{...metadata...}}}`. See the [HTTP contract](results.md#http-contract) and
[OGC review guide](validation.md#ogc-review-guide) for HTTP and standards context.

## Raster reprojection — `raster-warp`

Required inputs: `source` and `target_crs`. Targets are **EPSG:28992**,
**EPSG:4326** and **EPSG:3857**. Optional `resampling` is **bilinear** (default)
or **nearest**. The source requires a CRS. Rasterio/GDAL reprojects each band,
retaining source width/height and choosing the transform from the transformed
extent. Clients cannot specify target resolution, dimensions or extent.

Output is a GeoTIFF retaining band count/dtypes and nodata where applicable.
Use nearest-neighbour resampling for categorical data. Scalar choices support
[literal, qualified and HTTPS forms](inputs.md#scalar-input-references).
See [the result contract](results.md#http-contract) for value/reference delivery
and [the local-file client](inputs.md#process-a-local-file) for a working example.

## Sample points — `raster-sample-points`

Required inputs: `source` and `points`. The latter accepts a GeoJSON **Point**,
**MultiPoint**, or **FeatureCollection of Point features**, with **1–1,000 point
locations** in total. Coordinates are two-dimensional **[longitude, latitude]**
in WGS84. Within a FeatureCollection, each feature requires `type`, `geometry`
and object/null `properties`; an optional string/number `id` is preserved.
FeatureCollection-level metadata, including OGC Features links/counts/timestamps
and bbox, is accepted and ignored. A `crs` override remains unsupported; geometry
and individual Feature members retain their existing restrictions. For inline
object data, use the OGC qualified-value form:

```json
{
  "points": {
    "mediaType": "application/geo+json",
    "value": {
      "type": "FeatureCollection",
      "features": [{
        "type": "Feature",
        "properties": {"name": "sample"},
        "geometry": {"type": "Point", "coordinates": [5.12, 52.09]}
      }]
    }
  }
}
```

Rasterio transforms the points to the raster CRS and samples the containing
pixel, without interpolation. The source must have a CRS. Output is always a
FeatureCollection containing one Point feature per location in input order.
Point/MultiPoint inputs receive new empty properties objects, populated with
`value`, and no generated IDs. FeatureCollection inputs preserve IDs, geometry
and properties, adding/replacing `properties.value` with the selected band's
value. Masked, nodata, nonfinite and outside-raster samples are **null**.
Output coordinates remain WGS84.

For example, the GeoJSON value may also be:

```json
{"type":"MultiPoint","coordinates":[[4.836065,52.647618],[4.827911,52.645173],[4.834395,52.644807]]}
```

See the complete [MultiPoint request](../examples/sample-multipoint-request.json).
All three forms use the same sampler and output delivery; no geometry library
is required. The input schema's `oneOf` distinguishes actual GeoJSON value
shapes, not inline/reference transport. Single Feature objects and
FeatureCollections containing MultiPoint features are not currently accepted.

## Reclassify — `raster-reclassify`

Required inputs: `source` and `classes`, an array of **1–128** intervals:

```json
{"classes": [{"min": 0, "max": 10, "value": 1}, {"min": 10, "max": 100, "value": 2}]}
```

Each interval includes `min` and excludes `max`. Bounds must be finite and
`min < max`; overlaps are rejected, adjacency is allowed and order is irrelevant.
Class values must be int32 integers excluding **-2147483648**, the output nodata
sentinel. Unmatched, masked and nonfinite pixels become nodata. Output is a
one-band int32 GeoTIFF retaining source dimensions, transform and CRS; a missing
CRS is permitted. Classification uses NumPy comparisons on Rasterio's masked
band data. It does not infer breaks or copy unrelated source metadata.

## Polygonize — `raster-polygonize`

Required input: `source`. Optional `connectivity` is **4** (edge-sharing pixels,
default) or **8** (also corner-sharing). Rasterio/GDAL constructs polygons from
contiguous equal values in the selected band, excludes masked/nodata pixels and
transforms them to WGS84 longitude/latitude. GeoJSON features have a generated
numeric `id` and `properties.value` containing the raster class. An all-nodata
raster returns an empty FeatureCollection.

The source requires a CRS and an **int8, uint8, int16, uint16 or int32** band.
Float and wider integer bands are rejected to avoid silent GDAL truncation.
Reclassify continuous data first. Limits are **65,536 source pixels**, **4,096
features** and **16 MiB output**. Polygon complexity can consume memory inside
GDAL before features are yielded; the pixel bound therefore applies even to
rasters that might produce few features. There is no simplification, dissolve,
topology repair or target-CRS option. GeoJSON uses RFC 7946 ring winding.

## Input and output forms

`points` accepts `application/geo+json` or `application/json`, either as a
qualified inline value or a controlled HTTPS reference. `classes`, `band` and
`connectivity` accept direct JSON values, qualified values or HTTPS
`application/json` references. Each JSON parameter is limited to **256 KiB**,
including referenced content. HTTPS policies match the existing raster resolver;
Rasterio never opens client URLs. Arrays such as `classes` represent one
array-valued input (`maxOccurs: 1`), not repeated input occurrences.

Raw/value returns native `image/tiff` or `application/geo+json`. Document/value
returns `result.value`: TIFF is qualified base64, while GeoJSON is a JSON object
with `mediaType: application/geo+json`. Document/reference returns `result.href`
and `type`; raw/reference returns HTTP 204 with a `Link`. Download URLs end in
`output.tif` or `output.geojson` and share quotas and expiry. GeoJSON is not a
Shapefile archive. Its rendering in the external client still needs testing;
see [client interoperability](validation.md#client-interoperability).

## Run a local-file request

The JSON examples use placeholder public HTTPS source URLs. Replace the source
with your local file's base64 and, for sampling, edit the example point locations
or load your own Point FeatureCollection:

```bash
mkdir -p runtime-data
uv run python - <<'PY'
import base64
import json
from pathlib import Path

request = json.loads(Path("examples/sample-points-request.json").read_text())
request["inputs"]["source"] = {
    "value": base64.b64encode(Path("my-raster.tif").read_bytes()).decode("ascii"),
    "mediaType": "image/tiff",
    "encoding": "base64",
}
# Optional: replace the example points with a local GeoJSON file.
# request["inputs"]["points"]["value"] = json.loads(Path("points.geojson").read_text())
Path("runtime-data/sample-request.json").write_text(json.dumps(request))
PY
curl --fail-with-body http://localhost:5001/processes/raster-sample-points/execution \
  -H 'Content-Type: application/json' --data-binary @runtime-data/sample-request.json \
  --output sampled.geojson
```

Use `examples/reclassify-request.json` or `examples/polygonize-request.json`
and the corresponding execution endpoint in the same recipe. Inspect/edit class
ranges before reclassification; polygonization needs categorical integer data.
For a local chain, download the reclassified TIFF and submit its bytes as the
next source. A localhost HTTP result URL is not a permitted HTTPS input URL.

For a deterministic check using independently generated raster data:

```bash
uv run python scripts/smoke_inputs.py --base-url http://localhost:5001
```

Standards guidance is in [validation](validation.md#ogc-review-guide); integration
tests validate descriptions and applicable execute/results documents against
the unchanged official OGC schema snapshot.

Rasterio references: [point sampling](https://rasterio.readthedocs.io/en/stable/api/rasterio.sample.html),
[GDAL polygonization](https://rasterio.readthedocs.io/en/stable/topics/features.html)
and [geometry transformation](https://rasterio.readthedocs.io/en/stable/api/rasterio.warp.html#rasterio.warp.transform_geom).
