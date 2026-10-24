# Historical decision: Rasterio backend and project naming

Accepted on 2026-10-23, recorded at `db6135e` and implemented at `88a83a2`.
This is a completed decision and upgrade record, not an implementation plan.
Current behavior is documented in [architecture](architecture.md), [inputs](inputs.md)
and [results](results.md).

## Decision and rationale

The project became `geo-processes`, using Rasterio/GDAL for rasters and NumPy
for statistics. Rasterio was already part of the pygeoapi environment; using it
directly removed the additional Terrio backend. Metadata became an application-owned
contract, with independent processors, small adapters and tested OGC representations.
The decision was not a performance comparison between libraries.

The migration preserved bounded reprojection, synchronous execution, all four
warp response modes, result retention/downloads, deployment isolation and MIT
notices. Pixel/nodata/transform tests established behavior without requiring
byte-identical GeoTIFF encodings between backends. The later user-input milestone
replaced demo-only input with HTTPS and inline base64.

## Upgrade names and preserve results

These mappings are retained only for installations upgrading from the old names:

| Previous identifier | Replacement |
| --- | --- |
| `terrio-processes`, `terrio_processes` | `geo-processes`, `geo_processes` |
| `terrio-info`, `terrio-warp` | `raster-info`, `raster-warp` |
| `TerrioInfoProcessor`, `TerrioWarpProcessor` | `RasterInfoProcessor`, `RasterWarpProcessor` |
| `TERRIO_OUTPUT_DIR`, `TERRIO_RESULT_*` | `GEO_OUTPUT_DIR`, `GEO_RESULT_*` |
| `/var/lib/terrio/results` | `/var/lib/geo/results` |
| Backend-native information dictionary | [Application-owned metadata](raster-info.md) |

There are no compatibility aliases for the old process/package/environment names.
The GitHub repository still uses `Gouwe-Gozer/terrio-processes`; its name also
appears in published exception type URLs. Renaming the application did not rename
that repository or those identifiers.

The logical Compose volume remains `results`. Preserve an installation's existing
Compose project name when changing checkout names or upgrading images. The internal
mount-path change does not rename the Docker volume. Omit `--volumes` when stopping
an installation whose results should be retained. With the same canonical public
URL, retained unexpired result URLs keep their paths and timestamps.

## Historical validation

At the pivot checkpoint, 210 tests passed with 96.35% coverage. Both local and
container environments passed the six CRS/resampling combinations, all warp
representations, restart persistence and release isolation. A separate upgrade
check retained an issued result URL and checksum across the image change.
The reviewed Geonovum report had five diagnostics. These figures describe that
checkpoint, not the current test suite or a certification result.

Full migration sequencing and command transcripts remain in Git history:
`git show 8efb5d5:docs/rasterio-pivot.md`. Current checks and outstanding standards
gaps are in [validation](validation.md); proposed work is in the [roadmap](roadmap.md).
