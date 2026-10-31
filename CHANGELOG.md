# Changelog

## 0.1.0 — Unreleased

- Expose five Rasterio/GDAL processes through pygeoapi 0.24.0: raster information,
  reprojection, point sampling, range reclassification and categorical polygonization.
- Accept users' GeoTIFFs through bounded public HTTPS references or inline base64;
  support qualified JSON and referenced parameters with shared validation/errors.
- Deliver JSON, GeoTIFF and GeoJSON by value or, where supported, through expiring
  downloads, including document/reference and HTTP 204/Link representations.
- Support synchronous execution and durable asynchronous jobs using PostgreSQL
  and a separate bounded worker. Retain requests/results, fail interrupted jobs
  explicitly and expose status, results and filtered/paginated Job List endpoints.
- Make API/PostgreSQL/worker the normal development/release deployment, with an
  explicit synchronous-only opt-out and shared resource/security settings.
- Preserve JSON values, HTML-safe serialization and native responses across
  execution modes; prevent caching of dynamic job responses.
- Provide a standalone custom Python process example with explicit pygeoapi
  registration, shared API/worker installation and sync/async HTTP tests.
- Use `pyproject.toml` and `uv.lock` for local and image dependencies, preserving
  pinned build tools, base images and identical API/worker dependencies.
- Publish read-only sample point/polygon collections and a matching CC0 AHN4
  GeoTIFF; support Point, MultiPoint and point FeatureCollection sampling inputs.
- Correct discovery/pagination, exception representations, OpenAPI descriptions
  and inherited unsupported Features CRUD/CQL2 and Callback declarations without
  patching upstream or changing its global conformance state.
- Supply reproducible Geonovum and official CITE workflows, unmodified native
  reports, official HTML reports and public assessments of remaining limitations.
- Improve Swagger/ReDoc presentation and narrowly filter false metadata-locale
  warnings while preserving meaningful upstream diagnostics.
- Consolidate public user, contributor and operator guidance; archive historical
  investigations and obsolete report snapshots separately.

The public name is Raster Processes API and the repository is `raster-processes`;
Python distribution/import names remain `geo-processes` / `geo_processes`.
Origin attribution and original MIT terms are retained in [README](README.md),
[LICENSE](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md).
