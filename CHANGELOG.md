# Changelog

## 0.1.0 — Unreleased

- Publish the supplied points and a nearby raster-contained polygon through
  native read-only OGC Features collections, alongside the unchanged AHN4 TIFF.
- Accept collection-level Features metadata in sampling inputs and validate
  sample discovery, paging, media types and raster alignment.

- Preserve pygeoapi's JSON-LD landing catalogue instead of treating it as an
  ordinary JSON links document; guard unexpected JSON body shapes.

- Restore the ReDoc documentation page with a pinned compatible bundle through
  pygeoapi's template override, and cover HTML processor-name locale warnings.

- Filter pygeoapi's false metadata locale warnings and remove the unused
  AsyncAPI file setting from the image, retaining normal logging and translation.

- Accept GeoJSON Point and MultiPoint sampling inputs alongside point
  FeatureCollections, preserving the same WGS84 contract and point-count limit.

- Add synchronous point sampling, range reclassification and categorical
  polygonization, with explicit band/CRS/complexity limits and GeoJSON contracts.
- Reuse TIFF delivery for reclassification and extend shared expiry/quota/download
  handling to GeoJSON, without new dependencies or asynchronous infrastructure.

- Audit Core Requirements 1–46; fix scalar references, job exception URIs and
  descriptions, required landing links and traversable process pagination.
- Reuse shared reference/error handling with async managers and record the
  conditional checker findings instead of advertising unsupported responses.
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
