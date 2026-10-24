# Historical warp milestone — 2026-10-23

This milestone introduced file-producing processing before the
[Rasterio migration](rasterio-pivot.md) and [user-raster input contract](inputs.md).
Its original implementation used Terrio and a bundled demo identifier; neither
is part of the current public contract. Use [results](results.md) and
[architecture](architecture.md) for current behavior.

## Decisions carried forward

- Bound reprojection by retaining source dimensions and offering explicit CRS
  and resampling choices.
- Support native TIFF, qualified base64 and referenced output, including an
  empty HTTP 204 plus `Link` for raw/reference execution.
- Keep output representation with the processor, using an explicit response
  value and a narrow correction for upstream's fixed successful HTTP 200.
- Publish complete outputs atomically under opaque IDs; serialize writers,
  enforce expiry/quota and keep downloads independent of persistent OGC jobs.
- Use a non-root-owned named result volume within the hardened release stack.

## Historical evidence

The milestone had 197 passing tests and 96.40% coverage. Host and independent
container clients exercised all four output modes, opened downloaded TIFFs and
verified persistence across restart. Expiry, cleanup and release isolation were
also checked. Geonovum recorded five job/async diagnostics; no new CITE run or
certification was claimed.

Old package commands, preview-stack instructions and proposed next branches
have been removed. The full report remains available with
`git show 8efb5d5:docs/warp-milestone.md`. Current validation and proposed
extensions belong in [validation](validation.md) and the [roadmap](roadmap.md).
