# Changelog

## 0.1.0 — Unreleased

- Expose synchronous `raster-info` and `raster-warp` through pygeoapi 0.24.0,
  with Rasterio 1.4.3, NumPy 1.26.4 and application-owned metadata contracts.
- Accept users' GeoTIFFs through controlled HTTPS references or inline base64;
  bound request/raster sizes, validate staged data and clean inputs after use.
- Describe binary raster values using OGC conventions, independently of transport.
- Deliver warp results as native TIFF, qualified base64 or download references,
  with bounded storage, expiry, atomic publication and cross-worker locking.
- Provide a local-file inspection/reprojection/download command, a JSON exception
  URI catalogue and startup validation with effective configuration feedback.
- Retain hardened release deployment, independent-client smoke checks, quality
  tooling and reviewed Geonovum diagnostics using Node 24.
- Document operation contributions, current OGC limitations and client follow-up.
- Consolidate maintained documentation and archive superseded planning material.

## Project history

The service derives MIT-licensed infrastructure from `bkn-terrain-processes`.
Initial demo-only backend milestones were replaced by the Rasterio implementation
and user-raster inputs. See the [historical planning record](CODEX_HANDOVER.md)
and [backend/naming decision](docs/rasterio-pivot.md); previous detailed changelogs
remain in Git history. Predecessor validation and release numbers do not describe
this service.
