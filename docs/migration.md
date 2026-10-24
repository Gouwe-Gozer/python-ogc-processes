# Historical initial migration — 2026-10-23

This record concerns the initial derivation from `bkn-terrain-processes`, before
the current Rasterio backend and user-input contract. It is not setup guidance.
Use [development](development.md) and [architecture](architecture.md) for current work.

## Retained decisions

- Reuse the official pygeoapi package, explicit process registration, synchronous
  execution, quality tooling, CI and hardened release infrastructure.
- Preserve MIT copyright/licence notices and predecessor attribution.
- Remove the predecessor's BGT/PDOK calculations, domain fixtures and live-data
  checks while retaining and expanding reusable standards/HTTP tests.
- Keep processors/contracts separate from small adapters and let each operation
  own result formatting. Use an owned entrypoint and version-checked OpenAPI
  corrections instead of patching upstream source or shell scripts.

The pygeoapi 0.23.4 to 0.24.0 upgrade was tested before replacing the original
application logic. The first demo-only process used Terrio; it was subsequently
superseded by the [Rasterio migration](rasterio-pivot.md).

## Historical evidence

The predecessor baseline had 106 passing tests and 82.05% coverage. The initial
information-process checkpoint had 111 passing tests and 94.31% coverage, plus
configuration/OpenAPI, Compose, wheel, release isolation and HTTP checks.
Geonovum recorded four job/async diagnostics at that point. No new TEAM Engine
run or OGC certification was established by this milestone.

Superseded package commands, demo identifiers, local preview ports and pending
branch plans have been removed from this summary. The full recorded report is
available with `git show 8efb5d5:docs/migration.md`. Current compatibility fixes
and standards gaps are maintained in [architecture](architecture.md) and
[validation](validation.md), not inferred from this historical result.
