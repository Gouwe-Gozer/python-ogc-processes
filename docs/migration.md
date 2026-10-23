# Terrio info milestone — 2026-10-23

Phases 0–2 are implemented as a local, reviewable patch in the already-created
Terrio derivative repository. No commit, remote push, publication, or change to
the original BKN checkout was made.

## Baseline and compatibility

Before editing, `uv sync --locked --all-groups` installed the predecessor's
lockfile in `.venv`. The available host interpreter was 3.14; uv installed
Python 3.12.15 into this repository to respect the existing constraints.
Ruff formatting (31 files), Ruff lint and Bandit passed. The exact test command
was `uv run pytest --cov=bkn_terrain_processes --cov-report=term-missing --cov-fail-under=70`:
**106 passed, 0 failed, 0 skipped**, **82.05%** coverage. No live PDOK check
was run; the deterministic predecessor suite mocks its external retrievals.

The old HTTP suite confirmed native JSON raw output, summary-keyed qualified
inline document output, sync-only descriptions, rejected callback/output
options, and ignored async preference without a false job URL. The generated
OpenAPI and compatibility code were inspected before replacement.

The **pygeoapi 0.23.4 → 0.24.0 upgrade succeeded**. It was tested separately,
while the BKN application and its workarounds were still intact: **106 passed**.
Then Terrio 0.4.2 was installed with source builds disabled. Its cp310-abi3
manylinux x86_64 wheel worked with Python 3.12, both locally and in Docker.
`terrio.info(path, stats=True)` returns a dictionary, verified on a real raster.
Python 3.12 was retained to match the tested official image; no assertion of
Python 3.14 incompatibility is made.

## What changed

Retained: official pygeoapi, BaseProcessor registration, configuration layout,
synchronous execution model, raw/document contract discipline, coverage floor,
Ruff/Bandit/pre-commit dependencies, CI, Compose hardening, discovery/isolation
scripts and the separate CITE echo fixture. The copy had no pre-commit hook
configuration, so a local-hook configuration now runs its existing tools.
Required copyright and MIT notices remain; new project metadata identifies
Gouwe-Gozer.

Removed from the derivative: BGT geometry/classification/PDOK calculations,
coordinate/radius inputs, domain-specific tests/data/examples and live-PDOK CI.
The baseline passed before removing this retired domain. Standards and manager
HTTP tests were adapted and expanded. Historical CITE reports remain explicitly
marked as predecessor evidence.

Refactored: the package is `terrio_processes`; each operation owns its contract
and output representation. `engine.py` is a plain Terrio adapter without OGC
imports. The manager preserves media types/native values, delegates result
formatting, preserves typed 400/500 errors and sanitizes unexpected failures.
The request guard derives execution routes from registered resources.

Compatibility fixes still required by **0.24.0**, covered by regression tests:

- DummyManager still returns an `outputs` array for document responses and
  collapses processing failures to 400; the custom manager corrects this.
- Malformed JSON shapes still cause upstream attribute errors without the guard.
- Callback conformance is still unconditional; the public manager removes it.
- Generated OpenAPI still uses a landing-page schema for conformance, omits the
  process-list limit/description 404, and advertises 201 and generic execute
  options. The smaller version-checked application generator corrects these.
- OpenAPI generation mutates processor output metadata; processors receive a
  deep copy so `contentMediaType` remains in subsequent descriptions.

Upstream now omits job paths for synchronous managers and respects process
capability metadata. Those historical patch portions were removed. An owned
entrypoint replaces the old `sed` edit to upstream's startup script.

## Validation

Commands from the repository root (local uv cache/interpreter environment
variables were used because writes outside the project are restricted):

```bash
uv sync --locked --all-groups
uv run ruff format --check src tests scripts
uv run ruff check src tests scripts
uv run bandit -r src scripts -c pyproject.toml
uv run pytest --cov=terrio_processes --cov-report=term-missing --cov-fail-under=70
uv run pygeoapi config validate --config config/pygeoapi.yml
uv run python -m terrio_processes.openapi --output /tmp/terrio-openapi.yml
uv run pygeoapi openapi validate /tmp/terrio-openapi.yml
```

Final suite: **111 passed, 0 failed, 0 skipped**, **94.31%** application coverage.
One upstream Pydantic class-config deprecation warning remains. The real HTTP
tests required loopback networking outside the restricted sandbox; they were
rerun successfully with that access. Ruff and Bandit passed. Both public and
integration configurations and generated OpenAPI passed validation. All three
Compose configurations parse. The wheel builds offline and includes the raster.
Pre-commit configuration validation and the configured hooks were checked.

The offline official-schema tests cover process list/description, conformance,
execute request, results and exceptions. OpenAPI's `byte` format needs a base64
format checker: without it, the official schema's string and binary `oneOf`
branches both match every string. The stored schemas are unchanged. This does
not claim that every possible OGC input type has been validated.

The release image built and ran, with imports of Terrio 0.4.2 and pygeoapi 0.24.0
verified inside `/venv`. Discovery and both execution modes passed over HTTP.
The health check and actual non-root, read-only, no-mount, capability and
privilege controls passed. The pinned base image digest is in the Dockerfile;
local Python is 3.12.15 and image Python is 3.12.3. Base-image transitive
packages are pinned by the image digest rather than copied from the uv lock.

Geonovum 1.2.0 completed with **four known diagnostics**, recorded in its
[updated baseline](../validation/geonovum/README.md). The absence of job paths
and async 201 is deliberate. No new CITE/TEAM Engine session or formal OGC
certification is claimed. Host Node was absent; the static check ran in a
throwaway Node container. Initial checker attempts failed during npm dependency
installation in constrained temporary storage; the normal disposable-container
run completed.

## Try the running service

Port 5001 was already occupied. The new release was started with:

```bash
API_PORT=5002 PYGEOAPI_SERVER_URL=http://localhost:5002 docker compose --file compose.release.yml up --build --detach
curl --fail-with-body -H 'Content-Type: application/json' \
  --data '{"inputs":{"source":"demo-dem"}}' \
  http://localhost:5002/processes/terrio-info/execution
curl --fail-with-body -H 'Content-Type: application/json' -H 'Prefer: respond-async' \
  --data '{"inputs":{"source":"demo-dem"},"response":"document"}' \
  http://localhost:5002/processes/terrio-info/execution
```

Both return 200 and `application/json`, without `Location`. Raw is Terrio's
raster dictionary. Document is `{"info":{"value":{...}}}`. Representative values:
`size=[4,3]`, `crs.epsg=28992`, `min=1`, `max=12`, `mean=6.5`, `valid_count=12`.
The README has request/default examples; the OpenAPI UI is on `/openapi`.

## Input security and next decision

Only the inline identifier `demo-dem` resolves, through a fixed registry, to a
bundled read-only 352-byte GeoTIFF. Unknown identifiers, paths, URLs, references,
extra inputs, callbacks, unsupported formats and transmission modes are rejected
before Terrio executes. This is not full external input-reference support.

Before `terrio-warp`, choose a writable bounded output store, an externally
retrievable HTTP URL and retention/cleanup. Test document/reference output as
`{"result":{"href":"https://...","type":"image/tiff"}}` and download/open the
actual raster from another client. Raw/reference, if offered, requires empty
204 plus Link headers; omitted transmission means value and must be explicitly
handled. Revisit input-fetch restrictions and synchronous resource limits then.
No file delivery, async infrastructure or engine plugin system was added here.
