# terrio-warp milestone — 2026-10-23

Implemented on `feat/terrio-warp`, based on the merged info milestone
(`origin/main` at `375ad05`). This report records the implementation and
validation performed before committing the milestone.

## Behavior

The second public process reprojects `demo-dem` using Terrio 0.4.2's direct
Python binding. Clients choose EPSG:28992, EPSG:4326 or EPSG:3857, and nearest
or bilinear resampling (bilinear by default). The approved input registry is
shared with `terrio-info`. Paths, remote input references and uploads remain
unsupported. The info endpoint's response contract is preserved.

Output width and height match the source, bounding allocation; extent and pixel
size follow reprojection. This is a deliberate bounded-grid choice rather than
exposing resolution, extent or arbitrary Terrio options. Input file/sample and
output byte limits apply before publication.

All four single-output combinations are implemented and tested:

- raw/value: 200 with native `image/tiff` bytes;
- document/value: 200 JSON with a qualified base64 GeoTIFF value;
- document/reference: 200 JSON with a retrievable `result.href` and media type;
- raw/reference: 204 with empty body and a `Link` header.

Omitted response/output/transmission members retain the standard defaults.
`Prefer: respond-async` remains synchronous without a job Location. A small
explicit `ProcessResponse` value lets each processor choose its representation.
A Flask correction changes successful raw/reference execution to 204 because
pygeoapi 0.24.0 otherwise fixes successful execution at 200. Its private status
marker is removed from HTTP responses. No upstream source was edited.

## Storage and deployment

The image initializes a non-root-owned directory, and Compose mounts one
writable named result volume. UUID output names, isolated workspaces and atomic
rename prevent partial downloads. A Linux file lock serializes writers across
workers; downloads remain available. Default capacity is 64 MiB/256 results,
with a 16 MiB per-file publication limit and one additional staging file. Existing
unexpired results are not evicted; busy/full service conditions return JSON 503.

Default retention is 24 hours, configurable up to seven days. Reads enforce
expiry immediately; new writes and the explicit cleanup command remove expired
files and abandoned workspaces. Opaque URLs use the canonical configured public
API URL, not a client-controlled Host header. Missing/expired URLs return JSON
404. Named-volume data survives container restart and recreation.

Release hardening remains: UID/GID 10001, read-only root, 64 MiB ephemeral
`/tmp`, all capabilities dropped and no-new-privileges. The one dedicated output
volume is the intentional exception to the previous no-volume release policy;
isolation tests reject additional mounts or bind mounts. Release Compose also
sets 512 MiB memory, one CPU and 128 process limits. Gunicorn retains two sync
workers and its 30-second timeout. See [result lifecycle](results.md) for details.

## Verification

The merged baseline passed before editing: **111 passed**, **94.31% coverage**,
Ruff format/lint and Bandit clean. The final expanded suite passes:
**197 passed, 0 failed, 0 skipped**, **96.40% application coverage**. One upstream
Pydantic class-config deprecation warning remains.

Commands use the repository-local uv environment:

```bash
uv sync --locked --all-groups
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts
uv run bandit -r src scripts -c pyproject.toml
uv run pytest --cov=terrio_processes --cov-report=term-missing --cov-fail-under=70
uv run pygeoapi config validate --config config/pygeoapi.yml
uv run python -m terrio_processes.openapi --output /tmp/terrio-warp-openapi.yml
uv run pygeoapi openapi validate /tmp/terrio-warp-openapi.yml
```

Tests inspect actual rasters for each CRS/resampling choice and verify that
nearest and bilinear produce different reprojected samples. HTTP tests cover
all response forms, defaults, invalid options, canonical URLs, storage capacity,
expiry, safe filenames, refusal of symlinks/special files, concurrent writers,
cleanup after failure and sanitized server errors.

Both the host client and an independent Docker client executed all output
modes against the release container and downloaded/opened referenced GeoTIFFs.
An already-issued URL remained retrievable after a service restart. A result
created by the smoke test was backdated to simulate elapsed retention; its URL
returned JSON 404 and the container's cleanup command physically removed it.
The release isolation checks passed with the dedicated named volume.

CI now includes the same independent-container download and restart checks;
no remote CI run is claimed before this branch is pushed. Python remains 3.12,
pygeoapi 0.24.0 and Terrio 0.4.2. No dependency or lockfile change was required.
The image uses the already-tested precompiled Terrio wheel.

The pinned Geonovum run completed with **five known diagnostics**. The only new
finding is the missing async 201 for `terrio-warp`, which is synchronous. The
four earlier job/async diagnostics are unchanged. The exact observed report is
recorded in the [baseline](../validation/geonovum/README.md).

The official OGC binary schema has overlapping unrestricted-string and
base64-string branches. Document/value responses keep the normative qualified
base64 representation and are verified by the application schema plus real
GeoTIFF decoding. Reference results and discovery/request/error documents are
validated against the unchanged official schemas. See
[validation limits](validation.md). No new CITE run or formal certification is
claimed.

## Local demonstration

A separate Compose project was used on port 5003, leaving existing services on
other ports alone:

```bash
API_PORT=5003 PYGEOAPI_SERVER_URL=http://127.0.0.1:5003 \
  docker compose --project-name terrio-warp --file compose.release.yml up --build --detach
uv run python scripts/smoke_warp.py --base-url http://127.0.0.1:5003 --save-reference /tmp/warp-reference.txt
uv run python scripts/check_release_container.py --project-name terrio-warp
```

Example requests are in [warp-value-request.json](../examples/warp-value-request.json)
and [warp-reference-request.json](../examples/warp-reference-request.json).
The [README](../README.md) includes curl examples. A local preview may be stopped
with `docker compose --project-name terrio-warp --file compose.release.yml down`;
omit `--volumes` to preserve its results.

## Further work

The established lifecycle can support `terrio-hillshade` in a later branch.
Remote fetching, user uploads, authentication, object storage, async execution
and distributed coordination remain separate future decisions. Local dataset
identifiers are not presented as OGC external-input reference support.

For the current implementation and sequencing, see the [Rasterio pivot](rasterio-pivot.md),
[user-input milestone](inputs.md) and [roadmap](roadmap.md). This report records
only the completed demo-based Terrio warp work.
