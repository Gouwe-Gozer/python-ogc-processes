# Changelog

## 0.1.0 — Unreleased

- Accept users' own GeoTIFFs in both processes through controlled HTTPS
  references and qualified inline base64, retaining the demo shortcut.
- Bound downloads, decoding and temporary workspaces; verify TLS and public
  destinations on every redirect, and remove staged inputs after execution.
- Extend schemas, HTTP tests, independent-client smoke checks and documentation
  for user inputs, preserving output modes and recording remaining OGC gaps.
- Rename the project/package to `geo-processes`/`geo_processes` and processes to
  `raster-info`/`raster-warp`; migrate configuration, image references and CI.
- Replace Terrio with Rasterio 1.4.3 and NumPy 1.26.4, declaring and locking
  directly used libraries and removing Terrio from the runtime.
- Define application-owned raster metadata, portable nodata/null representations
  and exact finite masked statistics; verify multiband reprojection and limits.
- Record the accepted `geo-processes`/Rasterio pivot before implementation,
  retaining users' own rasters as the first useful-service milestone.
- Document the roadmap toward user-supplied data and raster/vector processes, with
  OGC review pointers, test evidence and explicit remaining conformance gaps.
- Add `raster-warp` for approved local GeoTIFFs, three target CRSs and
  nearest/bilinear resampling, with native, base64 and reference responses.
- Persist bounded results in a named volume with configurable 24-hour expiry,
  atomic publication, serialized writers, cleanup and HTTP downloads.
- Extend HTTP/schema/storage tests and CI with independent-container downloads,
  restart persistence and dedicated-volume isolation checks.
- Document the `geo-processes` identity, current implementation and historical
  validation separately, with explicit MIT origin attribution and maintainer
  copyright for Minnert Wijnands (Gouwe-Gozer).
- Derive the service from the reusable BKN pygeoapi infrastructure.
- Upgrade pygeoapi from 0.23.4 to 0.24.0 after a separate baseline test cycle.
- Initially implement Terrio 0.4.2 info/warp milestones, retained as historical
  reports; the Rasterio pivot supersedes their backend and public names.
- Preserve synchronous OGC raw/document semantics, schema and HTTP tests,
  coverage, Ruff, Bandit and hardened Compose deployment.
- Replace the BGT-specific OpenAPI patch and entrypoint modification with
  operation-specific contracts and an owned startup script.
- Remove BGT/PDOK calculations, examples and live-data CI checks.

The predecessor's releases remain in Git history; their version numbers and
validation reports do not describe this application.
