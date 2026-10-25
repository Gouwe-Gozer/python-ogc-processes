# Project history

This is historical context, not setup instructions or a development plan.
Use [architecture](architecture.md), [development](development.md),
[validation](validation.md) and [the roadmap](roadmap.md) for maintained guidance.

## Origins and retained decisions

The project derives pygeoapi integration, tests and deployment infrastructure
from MIT-licensed [`bkn-terrain-processes`](https://github.com/Gouwe-Gozer/bkn-terrain-processes).
The original notices and this project's copyright are preserved in
[LICENSE](../LICENSE) and [third-party notices](../THIRD_PARTY_NOTICES.md).
The predecessor's BGT-specific processing is not part of this service.

The initial 2026-10-23 prototypes used an additional raster backend and bundled
demo identifiers. They were replaced with Rasterio/GDAL and ordinary HTTPS or
inline base64 inputs. Rasterio was already present in the pygeoapi environment;
using it directly removed an unnecessary backend dependency.

The useful decisions are retained in the implementation: explicit pygeoapi
process registration, independent contracts/adapters, fixed-grid reprojection,
bounded input/output storage, all four file-delivery modes and a hardened
release image. Later additions introduced sampling, reclassification,
polygonization and read-only public samples. The Python distribution/import
names remain `geo-processes` / `geo_processes` under the Raster Processes API
public name and `raster-processes` repository.

## Earlier records

Superseded migration, backend, warp and naming instructions were consolidated
during housekeeping. Their pre-cleanup records remain available, for example:

```bash
git show 74d08d3:docs/migration.md
git show 74d08d3:docs/rasterio-pivot.md
git show 74d08d3:docs/warp-milestone.md
git show 74d08d3:docs/renaming.md
git show 74d08d3:CODEX_HANDOVER.md
```

Retained [CITE evidence](../validation/cite-teamengine/README.md) concerns the
predecessor's diagnostic echo process, not certification of this raster service.
Current standards evidence and limitations are documented in [validation](validation.md).
