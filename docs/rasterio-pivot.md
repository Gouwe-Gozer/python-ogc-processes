# Decision: pivot to geo-processes and Rasterio

Accepted on 2026-10-23. The project direction is **geo-processes**, a pygeoapi
service for processing **users' own geospatial data**, starting with rasters.
Rasterio replaces Terrio as the raster implementation. Shapely, Pyogrio and
GeoPandas can support later vector processes when those processes need them.

This decision is documented before implementation. At this checkpoint, the
running code is still the Terrio implementation described in the README.
The migration commit must update the runtime documentation and record its
validation here. The [roadmap](roadmap.md) describes subsequent service work.

## Why change direction

The pinned [pygeoapi dependencies](https://raw.githubusercontent.com/geopython/pygeoapi/0.24.0/requirements.txt)
already include Rasterio and Shapely. The existing environment therefore already
uses the GDAL ecosystem even though the two processing calls use Terrio's native
Rust binding. A completely GDAL-free deployment is no longer a project goal.

Using Rasterio directly fits the intended raster/vector Python ecosystem and
removes an additional processing dependency. This decision is about the service
we intend to build; it is not a performance or correctness comparison of the
libraries. Algorithm coverage and numerical behavior must be checked per process.

## Migration scope

1. Rename the Python project to `geo-processes`, its package to `geo_processes`,
   and the public processes to `raster-info` and `raster-warp`. Update imports,
   configuration, image metadata, examples, commands, tests and CI together.
   The GitHub remote keeps its existing name until the owner renames it.
2. Implement information/statistics and bounded reprojection using Rasterio.
   Define an application-owned JSON metadata contract rather than exposing a
   library's native dictionary as the permanent API. Preserve supported CRS and
   resampling choices, the bounded grid and meaningful raster validation.
3. Remove Terrio from active source, dependencies, container installation and
   test/smoke tooling. Declare directly used libraries explicitly in project
   dependencies; commit the lockfile with dependency changes. Verify the image's
   Rasterio/GDAL environment rather than assuming it matches the host lockfile.
4. Retain OGC discovery, synchronous execution, four warp response/transmission
   combinations, bounded output storage, expiry, downloads, hardened deployment
   and applicable tests. Validate raster pixels, nodata and transforms as well
   as HTTP representations. Do not require byte-identical GeoTIFF encodings
   across different processing libraries.
5. Update active documentation and dependency notices. Preserve the MIT licence,
   original copyright notices, BKN origin attribution and accurate historical
   milestone/validation reports. Historical Terrio references need not be erased.

This is an intentional pre-release API/package rename. Existing execution URLs,
imports and deployment names will change; no compatibility aliases are planned.
Changing a result-volume name must not silently discard earlier outputs. Document
how to retain or deliberately replace storage before changing deployment names.

## Boundaries and follow-up

The pivot does not implement input references or uploads. Processing users' own
rasters remains the first useful-service milestone **after this migration**.
An operator catalogue remains optional. See the [input plan](roadmap.md#user-supplied-rasters).

Add vector libraries when an implemented operation needs them. Keep independent
process contracts and small Python adapters; do not introduce an engine plugin
framework or assume every GDAL algorithm has a direct Rasterio equivalent.
Reassess hillshade and other candidate algorithms against available libraries.
Async execution and distributed storage remain separate workload decisions.

Changing the raster library does not confer OGC compliance. Follow the
[OGC review guide](validation.md#ogc-review-guide), preserve honest capability
claims and explicitly track input-reference and job-resource gaps.

## Branch and commit sequence

- `refactor/rasterio-pivot` starts from the tested warp checkpoint `0b6de7c` on
  `feat/terrio-warp`. It depends on that branch until the warp work is integrated
  into `main`; the pivot should not be presented as an independent change.
- First commit: this accepted decision, the updated roadmap, OGC review guidance
  and working instructions. Runtime behavior remains unchanged at that checkpoint.
- Next commit: a coherent, validated Rasterio migration and library-neutral rename.
  Keep intentionally related dependency, contract, container and CI changes together.
- Keep the previous warp branch and existing history. Rebase the pivot onto the
  integrated warp result if needed after a squash merge; review the resulting diff.
  Pushing branches, merging and renaming the GitHub repository are separate actions.

## Validation status

Before migration, the unchanged Terrio baseline has 197 passing tests and 96.40%
coverage, plus passing Ruff and Bandit checks. A local, in-memory Rasterio
feasibility check reads the fixture's exact statistics and produces valid
4 by 3 GeoTIFFs for all six current CRS/resampling combinations. These checks
establish feasibility only; they are not the migrated service's test results.
