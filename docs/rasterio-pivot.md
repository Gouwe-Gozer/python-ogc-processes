# Decision: pivot to geo-processes and Rasterio

Accepted on 2026-10-23. The project direction is **geo-processes**, a pygeoapi
service for processing **users' own geospatial data**, starting with rasters.
Rasterio replaces Terrio as the raster implementation. Shapely, Pyogrio and
GeoPandas can support later vector processes when those processes need them.

This decision was committed before implementation in `99383c1`. The migration
implements the scope below and updates the runtime documentation. The
[roadmap](roadmap.md) describes subsequent service work.

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
imports and deployment names change; no compatibility aliases are provided.

## Upgrade names and preserve results

| Previous name or behavior | Current name or behavior |
| --- | --- |
| `terrio-processes`, `terrio_processes` | `geo-processes`, `geo_processes` |
| `terrio-info`, `terrio-warp` | `raster-info`, `raster-warp` |
| `TerrioInfoProcessor`, `TerrioWarpProcessor` | `RasterInfoProcessor`, `RasterWarpProcessor` |
| `TERRIO_OUTPUT_DIR`, `TERRIO_RESULT_*` | `GEO_OUTPUT_DIR`, `GEO_RESULT_*` |
| `/var/lib/terrio/results` inside the container | `/var/lib/geo/results` inside the container |
| Terrio-native info dictionary | [Application-defined metadata](raster-info.md), including dtype names, nullable CRS/statistics and a tags object |

Update local environment settings, client URLs/imports, launch commands and any
image references. Previous environment variable names are no longer read.
The GitHub remote still points to `Gouwe-Gozer/terrio-processes`; the owner can
rename it separately. The repository directory can retain its existing name.

The logical Compose volume remains `results`. Its Docker name depends on the
Compose project, so **retain the previous project name** when upgrading an
existing installation. An internal mount-path change does not rename that
volume. For the default project created from this repository's existing folder:

```bash
docker compose --project-name terrio-processes --file compose.release.yml up --build --detach
```

If the installation used a custom project name, supply that same name instead.
Keep using it after renaming the checkout directory. Do not add `--volumes` to
`down` when retaining results. Unexpired files keep their original timestamps
and `/results/<id>/output.tif` URLs when the canonical server URL is unchanged.
An isolated old-image to new-image test verified an issued URL and identical
file checksum across the upgrade; it did not touch an existing user's volume.

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

The pre-migration Terrio baseline had 197 passing tests and 96.40% coverage.
The migrated implementation has **210 passing tests and 96.35% coverage**, with
Ruff formatting/lint and Bandit passing. The additional cases cover nodata and
non-finite samples, empty bands, missing/custom CRS, complex-raster rejection,
input bounds and multiband identity reprojection. Existing HTTP, schema,
storage, concurrency, expiry and error coverage is retained.

The checked application versions are pygeoapi **0.24.0**, Rasterio **1.4.3** and
NumPy **1.26.4** on Python **3.12**. Rasterio/NumPy match the pinned base image;
using Rasterio 1.5 would also require NumPy 2, which is a separate dependency
upgrade. The local wheel bundles GDAL **3.9.3**, while the image uses GDAL
**3.11.4**. Both environments pass all six CRS/resampling combinations.

Additional verification:

- Public and integration configuration/OpenAPI validation, all Compose
  configurations and an offline wheel build/inspection pass.
- The self-contained release starts with no source/configuration host mounts.
  Runtime inspection confirms non-root execution, read-only root, dropped
  capabilities, no privilege escalation and the dedicated result volume.
- Discovery and all four warp response/transmission combinations pass through
  Gunicorn, the host client and an independent client container. An issued URL
  remains usable after restart. The old-image volume upgrade is verified above.
- Terrio and the old application module are absent from the new image; Terrio
  is absent from the local locked environment and wheel requirements.
- The pinned Geonovum checker completed against the migrated service. Its five
  diagnostics differ only in the two renamed execution paths; see the
  [reviewed baseline](../validation/geonovum/README.md).

The inherited upstream Pydantic deprecation warning remains. No remote CI run,
new TEAM Engine/CITE run or OGC certification is claimed. Input references and
uploads remain unimplemented. See the [OGC evidence boundary](validation.md).
