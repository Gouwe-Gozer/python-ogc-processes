# Reviewed Geonovum upgrade — 2026-10-25

The official npm registry's latest stable `@geonovum/ogc-checker` is **1.3.2**.
It supports approved OGC API – Processes Part 1 **1.0.0**, selected explicitly.
The [release changelog](https://github.com/Geonovum/ogc-checker/blob/v1.3.2/CHANGELOG.md)
describes the 1.3 diagnostic/source changes and Node >=22.18 requirement.

A run against the real five-process Raster Processes API returned the **same
eight diagnostics** as 1.2.0. Every code, path, message, severity, documentation
URL and normalized source was compared unchanged. Standard and ruleset lists
are also unchanged. The baseline diff is limited to:

- checker version `1.2.0` → `1.3.2`;
- the newly emitted `ruleset` conformance-class URI on each diagnostic.

These fields remain significant in comparisons; no new finding was accepted,
removed or hidden. Seven are conditional Core expectations for async/retained
job success that this synchronous non-retaining profile cannot exercise; one
concerns the unadvertised optional Job List class. Existing applicability analysis
remains in the [Core audit](../../docs/core-conformance-audit.md).

The default workflow uses Node **24.22.1** / npm **11.19.1** in the immutable image
specified in `scripts/check_geonovum_baseline.py`. `package-lock.json` fixes
transitive tool dependencies. These are validation-only packages, excluded from
the application image. CI and `make validate-geonovum` use the same command.

This metadata-only baseline migration is an explicit PR-review proposal. Normal
commands do not invoke `--update-baseline` or rewrite reviewed evidence.
