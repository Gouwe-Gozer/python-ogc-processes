# Raster information contract

`raster-info` returns application-defined JSON backed by Rasterio/GDAL and
NumPy. It does not expose a library's native metadata dictionary. The executable
schema is [contracts/info.py](../src/geo_processes/contracts/info.py).

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

Both current raster operations enforce 16 MiB per input and 1,048,576 samples
including bands. Info reads one band at a time for exact statistics. It can
inspect a raster without a CRS; warp rejects that raster. Both processes accept
[user GeoTIFFs](inputs.md) through HTTPS references or inline base64. Source files are validated
and staged privately; metadata and all statistics refer to the supplied file.

Raw execution returns this object directly. Document execution returns
`{"info":{"value":{...metadata...}}}`. See the [README](../README.md) and
[OGC review guide](validation.md#ogc-review-guide) for HTTP and standards context.
