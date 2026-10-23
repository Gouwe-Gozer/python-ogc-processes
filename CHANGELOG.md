# Changelog

## 0.1.0 — Unreleased

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
