# Changelog

## 0.1.0 — Unreleased

- Record the accepted `geo-processes`/Rasterio pivot before implementation,
  retaining users' own rasters as the first useful-service milestone.
- Document the roadmap toward user-supplied data and raster/vector processes, with
  OGC review pointers, test evidence and explicit remaining conformance gaps.
- Add `terrio-warp` for approved local GeoTIFFs, three target CRSs and
  nearest/bilinear resampling, with native, base64 and reference responses.
- Persist bounded results in a named volume with configurable 24-hour expiry,
  atomic publication, serialized writers, cleanup and HTTP downloads.
- Extend HTTP/schema/storage tests and CI with independent-container downloads,
  restart persistence and dedicated-volume isolation checks.
- Document the `terrio-processes` identity, current implementation and historical
  validation separately, with explicit MIT origin attribution and maintainer
  copyright for Minnert Wijnands (Gouwe-Gozer).
- Derive Terrio Processes from the reusable BKN pygeoapi infrastructure.
- Upgrade pygeoapi from 0.23.4 to 0.24.0 after a separate baseline test cycle.
- Add the direct Terrio 0.4.2 adapter, offline GeoTIFF and `terrio-info` process.
- Preserve synchronous OGC raw/document semantics, schema and HTTP tests,
  coverage, Ruff, Bandit and hardened Compose deployment.
- Replace the BGT-specific OpenAPI patch and entrypoint modification with
  operation-specific contracts and an owned startup script.
- Remove BGT/PDOK calculations, examples and live-data CI checks.

The predecessor's releases remain in Git history; their version numbers and
validation reports do not describe this application.
