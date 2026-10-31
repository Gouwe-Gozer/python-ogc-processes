# Three-process contributor experience evaluation

Evaluated on 2026-10-31 from `chore/contributor-experience`, on disposable
branch `experiment/three-process-contributor-evaluation`. No commit, push or
publication was made. The default configuration and contributor documentation
are unchanged. The opt-in configuration adds three resources to a disposable
copy of the normal catalogue.

Starting commit: `736d6be6758e22b7b9a839ad4b10856af3fa5edc`.

## How the integration path was discovered

The [README](../../README.md) links directly to
[adding a process](../../docs/adding-a-process.md) and the independent
[text example](../custom-process/README.md). Together with [AGENTS.md](../../AGENTS.md),
[CONTRIBUTING.md](../../CONTRIBUTING.md), [development](../../docs/development.md),
[architecture](../../docs/architecture.md), [validation](../../docs/validation.md)
and [resource settings](../../docs/release-image.md#resource-configuration),
these provided a usable route from a function to an installed process.

I followed the in-repository operation/contract/direct-`BaseProcessor` layout,
explicit dotted registration, deep-copied metadata and existing result/OpenAPI
hooks. I adapted `test_custom_process.py` and the actual-worker lifecycle fixture
in `test_async_containers.py`. Reading these examples and the existing raster
wrappers was necessary; knowledge of earlier development decisions was not.

## Files

Paths in this table are relative to `src/geo_processes/`.

| Integration | Processing function | Contract | Direct wrapper | Additional data |
| --- | --- | --- | --- | --- |
| Geometry intersection | `operations/intersection.py` | `contracts/intersection.py` | `processes/intersection.py` | None |
| Raster datatype conversion | `operations/convert_dtype.py` | `contracts/convert_dtype.py` | `processes/convert_dtype.py` | None |
| Terrain analysis | `operations/terrain.py` | `contracts/terrain.py` | `processes/terrain.py` | `data/terrain/gemeente_alkmaar.geojson`, `data/terrain/README.md` |

Other new files:

- `examples/contributor-experience/processes.yml`: three opt-in registrations.
- `examples/contributor-experience/compose.yml`: common API/worker image and
  config mount, 300-second sync/async deadlines for this experiment.
- `examples/contributor-experience/{intersection,convert-dtype,terrain}-request.json`:
  executable examples; `REPORT.md`: this evaluation and reproduction commands.
- `tests/test_contributor_processes.py`: operation, validation, schema, manager
  and Flask HTTP tests, plus the opt-in live PDOK function test.
- `tests/test_contributor_containers.py`: actual HTTP/API/PostgreSQL/worker tests.
- `tests/fixtures/terrain_pdok.py`: deterministic public-source responses with
  known areas; `tests/fixtures/pdok_startup/sitecustomize.py`: test-only transport
  replacement inherited by API and spawned worker children.

Modified files:

- `pyproject.toml`, `uv.lock`: directly declare Shapely 2.1.2, PyProj 3.7.2 and
  Requests 2.34.2, all already present at these versions transitively. No package
  version changed. Rasterio/NumPy required no additional dependency.
- `tests/test_async_containers.py`: add two opt-in fixture profiles, merge the
  registrations, and mount the deterministic transport only in the mocked profile.
- `THIRD_PARTY_NOTICES.md`: identify dependencies and supplied terrain materials.

## Test 1: Shapely geometry intersection

**Integration steps.** Implement a plain function accepting two GeoJSON geometry
objects, describe `left`/`right` inputs and the `intersection` output, resolve
qualified JSON or controlled HTTPS references, validate geometry structure and
topology, then call Shapely intersection. Register
`geo_processes.processes.intersection.GeometryIntersectionProcessor`.

The operation accepts bounded 2D CRS84 geometries, including collections, and
returns GeoJSON by value. It rejects invalid topology instead of repairing it.
Disjoint inputs produce an empty GeometryCollection. This is a planar operation;
geodesic and antimeridian handling are outside its contract.

**Obstacles/documentation.** Object inputs must use the documented
`{"value": geometry, "mediaType": "application/geo+json"}` envelope. A bare object
is not accepted by `resolve_json`; this is an explicit wire convention, not an
inability to process geometry. The JSON-only text example does not demonstrate
changing media type between raw GeoJSON and a JSON document. Returning a plain
dictionary from `format_result` retains the raw media type; `ProcessResponse`
sets the document's `application/json` explicitly. Existing file wrappers and
delivery code made this discoverable, but a contributor must inspect them.

**Shared infrastructure changes:** none. **Documentation-alone verdict:** yes,
for a Python/geospatial contributor willing to adapt the linked examples; the
non-default JSON media type is a small gap in the minimal example.

**Tests.** Known polygon intersections; point/line results; disjoint/empty
geometry; invalid rings, topology, coordinates and geometry types; input/output
errors; official process/execute/result schemas; generated OpenAPI; raw/document
HTTP results; actual-worker parity and failed-job errors.

## Test 2: Raster datatype conversion

**Integration steps.** Implement an independent all-band Rasterio/NumPy function,
declare dtype/policy/nodata inputs, reuse `resolve_source`, publish via
`ResultStore` and `FileOutput`, and reuse `format_file`. Declare `result_extension`
for download/OpenAPI integration. Register
`geo_processes.processes.convert_dtype.RasterConvertDtypeProcessor`.

Supported targets are `uint8`, `uint16`, `int16`, `float32`, `float64`.
The function preserves dimensions, all bands, CRS, transform, descriptions,
units, scale/offset, color interpretation and default-namespace descriptive tags.
It drops stale statistics, overviews and dtype-dependent creation options.
Compression/layout and arbitrary metadata domains are not promised to survive.
Palette and GCP/RPC georeferencing are explicitly rejected by this operation.

Overflow defaults to an error; `overflow=clip` is explicit. Float-to-integer
conversion defaults to truncation toward zero; `rounding=nearest` uses ties to
even. Float casts use normal IEEE rounding. Nonfinite unmasked pixels reject.
Nodata is retained only when exactly representable, otherwise the caller must
supply destination `nodata`. Masks without a source sentinel also require one.
Converted valid pixels colliding with the sentinel reject, including collisions
introduced by rounding or clipping. Per-band validity survives through nodata;
no external mask sidecar is required.

**Obstacles/documentation.** The raster helpers are well documented and reusable.
The existing file-contract helper also inserts a single-band selector; this
all-band process removes that property from its own generated request schema.
No helper change was necessary. Choosing numerical conversion semantics and
which metadata remain meaningful is operation design, not framework friction.

**Shared infrastructure changes:** none. **Documentation-alone verdict:** yes.
This is the most natural integration because the documented examples already
exercise bounded TIFF input and file delivery. The policies still require
Rasterio/NumPy expertise; the framework cannot decide them for a contributor.

**Tests.** All five destination types; multiband values and masks; grid and
descriptive metadata; rounding; clipping/error overflow; nodata remapping and
collisions; NaN nodata; unmasked NaN/Infinity; float32 overflow; internal masks;
nodata-free integer boundaries; invalid policies and formats; process/OpenAPI
schemas; synchronous and actual-worker raw/document and value/reference modes,
independent downloads, and typed failed-job results.

## Test 3: Existing terrain analysis

**Integration steps.** Extract `get_terrain_analysis()` and
`load_alkmaar_polygon_rd()` with their supporting imports, logger, CRS transforms
and municipality-path constant. Remove FROST functions, `ingestion.client`,
`ingestion.config`, settings access, warning suppression, log-directory creation
and interactive `__main__` behavior. Package the supplied GeoJSON and adjust only
its relative path. Import the operation at execution time so processor discovery
does not initialize the original module's transforms or load the dataset.
Declare the function parameters/output structure and register
`geo_processes.processes.terrain.TerrainAnalysisProcessor`.

Python AST comparison against the supplied script confirmed that **both extracted
functions, including all nested helpers, are identical**. Ruff changed formatting,
not their logic. Classification, repeated WGS84/RD transformations, union,
priority masking, rounding, partial-fetch reporting and every output key remain.
No missing processing implementation was invented. The original defaults
300/500 metres and limit 1000 remain. The wrapper explicitly scopes requests to
a Netherlands bounding box, ordered radii 1–500 metres, and limit 100–1000;
the labels `buffer_300m`/`buffer_500m` remain even for custom radii, as originally.

**Dependencies/data/runtime.** Shapely/GEOS, PyProj/PROJ and Requests/TLS are
required. No GeoPandas, FROST client/configuration or credentials are needed.
The supplied WGS84 municipality Feature is the only auxiliary dataset. The
existing image copies its package path to both services. Live execution requires
DNS, trusted CA certificates and public HTTPS access to five fixed PDOK BGT
collections (`begroeidterreindeel`, `onbegroeidterreindeel`, `waterdeel`, `wegdeel`,
`pand`). The original `/lv/bgt/` URLs currently redirect to the
[PDOK BGT catalogue](https://api.pdok.nl/kadaster/bgt/ogc/v1/collections?f=json);
the original Requests redirect behavior is retained. PROJ network downloads are
not needed for the tested transforms.

Original script SHA-256:
`5f47b73ae2f5eb589a32679b97614cad82ca7716c9d1755f3d7fbbdfacc022a5`.
Supplied/copy boundary SHA-256:
`00e52b1c9f5ae85e9e28867eccc02d5328ac94970a5a4a786048d7ecde6055c9`.
No licence was stated in either supplied material; this experiment does not
assert a new licence for them.

**Original-code problems, preserved rather than fixed:**

- A 30-second timeout applies to each request, not the whole analysis. Tile
  subdivision repeats without an iteration/request/feature/response-byte cap.
  Five sources and retries can exceed a 30-second service deadline. Radii and
  limit validation do not prove a total workload bound.
- Feature deduplication uses IDs within a source (missing IDs collapse to `None`)
  and one geometry-WKT set across all categories. A duplicate geometry first
  encountered as vegetation can discard a building before building priority is
  applied. A deterministic regression demonstrates this behavior.
- Invalid features can be logged and skipped while `is_partial` stays false;
  a deterministic regression demonstrates this. Partial status tracks fetch
  failures, not complete analytical reliability.
- Requests JSON decode errors inherit `RequestException`, so the first handler
  labels them `http_error`, rather than `parse_error`. Tested and preserved.
- Code inspection shows the non-priority categories are subtracted from the
  priority union but not from each other. Overlapping low vegetation, water or
  bare ground can therefore contribute to overlapping percentages. Category
  fallback and combined `onverhard` semantics also remain the author's choices.

**Application limitations, distinct from those problems.** The worker has a hard
300-second maximum deadline, one executing job, and a fresh child per job. The
shared 512 MiB image/environment and lack of per-process timeout policy are
documented constraints. This experiment raises deadlines in its own Compose
override, not shared code. An unbounded source algorithm is not guaranteed to
finish inside these limits. Its successful partial result remains HTTP 200/
successful job with `is_partial=true`; no wrapper silently treats missing
sources as complete or rewrites the numerical result.

**Obstacles/documentation.** The documented configuration/data packaging and lazy
execution guidance were sufficient. Separating unrelated FROST side effects and
identifying the original workload risks required reading the supplied software.
The text example has no external-service mocking recipe for spawned worker
children. The existing container fixture was reusable, but deterministic PDOK
transport required an explicit test-only Python startup hook mounted into both
services. This hook never enters the production image or manual deployment.

**Shared infrastructure changes:** none; only the existing test fixture gained
experiment profiles. **Documentation-alone verdict:** sufficient to integrate,
register and deploy the complete supplied function; insufficient to establish
that its algorithm is correct or always fits the service's workload limits.
Those require domain review and operational measurements.

**Tests.** Deterministic square areas verify category mapping, priority masking
and original statistics in both buffers. HTTP/JSON failures, tile subdivision/
deduplication, invalid features and missing municipality data are covered.
Discovery, descriptions, OpenAPI, synchronous results, actual-worker parity and
failed-job validation are exercised. Separate live tests use 30/50-metre Alkmaar
buffers, with all five sources responding and positive building coverage, through
the function, synchronous API and actual worker. This small live probe does not
prove worst-case runtime or survey accuracy for default 300/500-metre buffers.

## Verification results

| Check | Result |
| --- | --- |
| `uv sync --locked --all-groups` | Passed; 72 packages resolved, 70 installed packages checked |
| `make test` | Passed: 680 passed, 121 opt-in tests skipped; coverage 79.71% (minimum 70%) |
| Ruff format/lint and Bandit | Passed as part of `make test`; no security findings |
| `pre-commit run --all-files` | All three hooks passed |
| Canonical and existing integration config/OpenAPI validation | Passed as part of `make test` |
| Disposable contributor config and generated synchronous OpenAPI CLI validation | Passed |
| Final opt-in contributor container suite, with live PDOK enabled | 14 passed in 88.81 seconds: 13 deterministic tests and 1 live sync/worker test |
| Separate live PDOK function probe | 1 passed; no failed sources |
| Three example requests against their generated schemas | Passed; intersection and raster examples also executed directly through the manager |
| Original/extracted function AST comparison; supplied/copied dataset checksum | Identical |
| `git diff --check` | Passed |

`make test` skips tests requiring explicitly enabled PostgreSQL/Docker/live
services. The new worker/live cases were run separately with their opt-in flags.
Existing broader PostgreSQL lifecycle, release, Geonovum and CITE suites were not
enabled: this experiment changes no shared execution lifecycle or conformance
claim. No reviewed OGC baseline was updated; existing CITE failures remain
unchanged. One existing Pydantic deprecation warning remains in the Python suite.

The first sandboxed full-suite attempt could not bind the existing loopback
HTTP/HTTPS fixture servers. The final successful run had socket access. An online
`uv add` attempt also hit sandbox DNS restrictions; declaring the already-locked
versions with `uv add --offline` succeeded. These are execution-environment
obstacles, not repository defects. Initial container assertions were corrected
to use the configured Swagger UI and semantic JSON equality (sync documents are
pretty-printed; persisted async documents use compact JSON).

Generated logs, configuration and OpenAPI stay under ignored `runtime-data/`:
`contributor-make-test.log`, `contributor-container-verified.log`,
`contributor-container-verified/async-containers*/commands.log`, and
`contributor-experience/{pygeoapi,openapi}.yml`. The default catalogue remains the
original five processes. Automated test projects were torn down with their
disposable volumes; no pre-existing deployment was changed.

## Reproduce this opt-in deployment

From the repository root on this disposable branch:

```bash
UV_CACHE_DIR=.uv-cache uv sync --locked --all-groups
mkdir -p runtime-data/contributor-experience
uv run python - <<'PY'
from pathlib import Path
import yaml
config = yaml.safe_load(Path("config/pygeoapi.yml").read_text())
config["resources"].update(yaml.safe_load(Path("examples/contributor-experience/processes.yml").read_text()))
Path("runtime-data/contributor-experience/pygeoapi.yml").write_text(yaml.safe_dump(config, sort_keys=False))
PY
API_PORT=5004 PYGEOAPI_SERVER_URL=http://localhost:5004 \
  docker compose -p raster-contributor-experience \
  -f compose.release.yml -f examples/contributor-experience/compose.yml up --build --wait
```

Inspect `/processes?f=json`, `/processes/{id}?f=json`, `/openapi?f=json` and
`/openapi?f=html`. Submit the matching example with `Content-Type: application/json`
to `/processes/{id}/execution`; add `Prefer: respond-async`, poll its `Location`
until successful/failed, and retrieve `{Location}/results` for the actual worker.
For example:

```bash
curl --fail-with-body http://localhost:5004/processes/terrain-analysis/execution \
  -H 'Content-Type: application/json' -H 'Prefer: respond-async' \
  --data-binary @examples/contributor-experience/terrain-request.json
uv run pytest tests/test_contributor_processes.py -q
GEO_TEST_ASYNC_CONTAINERS=1 uv run pytest tests/test_contributor_containers.py -q
GEO_TEST_LIVE_PDOK=1 uv run pytest tests/test_contributor_processes.py -k live_pdok -q
GEO_TEST_ASYNC_CONTAINERS=1 GEO_TEST_LIVE_PDOK=1 \
  uv run pytest tests/test_contributor_containers.py -k live_pdok -q
make test
```

Automated container tests use unique `raster-async-test-*` projects and remove
only their own resources. Stop the manual example with the same environment,
project and Compose arguments followed by `down`. Its named volumes are retained.

## Critical assessment

The repository meets its extensibility goal for bounded trusted Python functions
that fit one installed environment: all three integrations use direct pygeoapi
interfaces without routing, dispatch, manager, worker, storage or schema-engine
changes. Non-raster vector analysis is demonstrably possible. The guides state
the boundaries and provide a working route through actual async execution.

The contributor experience is competent but requires application integration
work: explicit schemas, semantic validation, two service-specific hooks, deployment
consistency and meaningful operation/HTTP tests. The minimal text example does
not cover media-type switching, all-band use of the raster schema helper, or
external-service mocks across spawned children. These are discoverability gaps,
not reasons to introduce a new abstraction layer. Existing processing software
with side effects or unbounded network work requires extraction and workload
review. The terrain experiment validates integration mechanics while leaving
visible the source algorithm's analytical and runtime weaknesses; it does not
justify presenting that algorithm as production-ready.
