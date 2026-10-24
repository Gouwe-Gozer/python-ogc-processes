# Historical planning record

This file archives the project's initial planning and migration checkpoints.
It is **not the source of truth for current behavior, development rules or the
next task**. Use the [README](README.md), [development guide](docs/development.md),
[architecture](docs/architecture.md) and [OGC validation guide](docs/validation.md).
Working rules belong in [AGENTS.md](AGENTS.md); future work belongs in the
[roadmap](docs/roadmap.md).

## Historical checkpoints

- The repository began as a copy of the MIT-licensed `bkn-terrain-processes`,
  reusing its pygeoapi, testing and deployment infrastructure. Origin attribution
  and notices remain in [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- The initial Terrio-backed information and warp milestones established separate
  processors, explicit OGC representations and bounded result storage. Their
  condensed records are [migration](docs/migration.md) and [warp](docs/warp-milestone.md).
- The Rasterio/backend and library-neutral naming decision was recorded at
  `db6135e`, then implemented on `main` at `88a83a2`. See the historical
  [decision and upgrade notes](docs/rasterio-pivot.md).
- User-raster inputs were integrated at `244667a`: HTTPS references and inline
  base64 replaced the demo-only input contract.
- Service usability work was integrated at `8efb5d5`: the local-file example,
  JSON exception catalogue, startup validation and contribution guide.

These checkpoints record completed work, not active branches or pending merge
instructions. Older detailed planning and command transcripts remain available
in Git history, for example `git show 8efb5d5:CODEX_HANDOVER.md`.
