# Codex handover — Terrio-backed OGC API – Processes

**Prepared:** 2026-10-23  
**Working title:** `terrio-processes`  
**Starting point:** [Gouwe-Gozer/bkn-terrain-processes](https://github.com/Gouwe-Gozer/bkn-terrain-processes)  
**Upstream dependencies:** [geopython/pygeoapi](https://github.com/geopython/pygeoapi) and [opengeos/terrio](https://github.com/opengeos/terrio)

## 1. Mission

Turn the reusable infrastructure of the existing BKN terrain-processing prototype into a small, maintainable **OGC API – Processes** service powered by **Terrio**.

**Reuse the existing BKN codebase as a template; do not start from pygeoapi's HelloWorld example and do not fork pygeoapi or Terrio.** The old BGT/PDOK land-cover calculation is no longer the desired processing engine. Keep the useful standards-aware integration work, tests and deployment discipline; replace domain-specific logic with independent Terrio operations.

The first tangible outcome should be a working, documented **`terrio-info`** process backed by Terrio's Python API, with real HTTP integration tests. File-producing operations (`terrio-warp`, then `terrio-hillshade`) follow as separate steps because they introduce output storage and delivery requirements.

This is an incremental migration, **not** a request to implement the entire Terrio CLI through HTTP in one pass.

## 2. Decisions already made

1. **Framework:** Keep pygeoapi.
2. **Engine:** Use the published Python package via `import terrio` (Rust-powered PyO3 bindings). Do not invoke the Terrio CLI via `subprocess` unless a concrete limitation is discovered. There is no expected performance advantage to a subprocess.
3. **Dependency boundaries:** Keep Terrio and pygeoapi as independently versioned upstream dependencies. Any integration code belongs to our own Python package, not in their sources.
4. **Execution:** **Synchronous only for the initial bounded processes**, as with the BKN prototype. Advertise only supported `jobControlOptions` / `outputTransmission`. Do not advertise working async job endpoints or callbacks if they are unavailable. Reassess execution limits before accepting large rasters or point clouds.
5. **Packaging:** Python 3.12, existing `uv`-based development workflow, Docker/Compose for deployment. Install Terrio in the **same Python environment used by pygeoapi's server**, not on the host or accidentally in a second virtual environment.
6. **Operations:** Expose narrowly defined, validated OGC processes, not arbitrary CLI commands or unconstrained user-selected Terrio functions/options.
7. **Scope discipline:** First get a reliable JSON-only process running. Do not solve distributed jobs, Kubernetes, object storage, arbitrary remote data access, and all Terrio operations as part of the first milestone.

## 3. Repository facts: inspect these files first

The existing BKN repository is an application built **on top of** pygeoapi, not a pygeoapi fork. At the time of writing it pins **pygeoapi 0.23.4** in `pyproject.toml` and the official pygeoapi Docker base image.

| Existing file | What it does | Migration treatment |
|---|---|---|
| `src/bkn_terrain_processes/process.py` | `BaseProcessor` implementation and execution entry point | Use the plugin pattern; replace BGT-specific process |
| `src/bkn_terrain_processes/process_contract.py` | Rich metadata, schemas and execution-contract declarations | Preserve the *pattern*, replace process-specific definitions |
| `src/bkn_terrain_processes/manager.py` | `OgcSynchronousManager`, based on `DummyManager`, with raw/document result normalization and option checks | **Keep initially**, test carefully against the selected pygeoapi version |
| `src/bkn_terrain_processes/app.py` | Flask request boundary guard, currently hardcoded to `/processes/bgt-land-cover-summary/execution` | Generalize to registered Terrio process endpoints if still necessary |
| `scripts/patch_pygeoapi_openapi.py` | BGT-specific generated-OpenAPI corrections | **Do not copy blindly**; re-evaluate each correction on newer pygeoapi |
| `config/pygeoapi.yml` | Server, manager and processor configuration | Retain structure; replace BGT identity, resource and imports |
| `docker/Dockerfile` | Pinned pygeoapi image; modifies upstream entrypoint to apply OpenAPI patch | Retain deployment concept, **remove brittle patching if no longer needed** |
| `compose.yml`, `compose.release.yml`, `compose.integration.yml` | Development, hardened release and integration setups | Reuse; adapt image, mounts and eventual output directories |
| `tests/`, `validation/`, `.github/` | Unit, HTTP/API contract, conformance/validation and CI work | Reuse the methods; remove or rewrite old BGT assertions |
| `src/bkn_terrain_processes/terrain_analysis.py` and BGT-specific input/PDOK logic | Former application domain | Remove from new application when no longer referenced |

**Important gotcha:** The existing manager assumes a processor result shaped like `{"id": "<output-id>", "value": ...}` and handles **one JSON result**. It is useful for `terrio-info`; it is not automatically sufficient for generated GeoTIFF/GeoPackage/COPC outputs. The OpenAPI patch and Flask guard also contain BGT-specific paths and schemas.

The original repository is a fork of `ITBreinstein/bkn-terrain-processes`. Preserve relevant license, copyright and third-party notices for any reused code. Prefer a **new repository derived from its reusable contents**, while leaving the original BKN project intact. If Codex is running inside the existing BKN checkout, use a dedicated feature branch and **do not delete the historical implementation or push to any remote without approval**.

## 4. Desired architecture

```text
HTTP client
    |
    v
pygeoapi (official upstream package)
    |
    +-- OGC processor class(es) and process metadata
    |       [our package; input validation, contract, result mapping]
    |
    +-- Optional custom synchronous manager / request guard
    |       [our package; only if upstream behavior needs correction]
    |
    v
Our engine adapter (plain Python, no pygeoapi imports)
    |
    v
terrio Python package -> compiled Rust extension
```

Keep the **Terrio invocation independent of the OGC interface**, e.g. conceptually:

```python
# Example only: validate the actual installed Terrio API first.
import terrio


def raster_info(source_path: str) -> dict:
    return terrio.info(source_path, stats=True)
```

That function should be trivially unit-testable without HTTP. The process class should then validate inputs, resolve a safe source path, call the engine function and express the result using the pygeoapi processor contract.

A possible eventual layout (adapt rather than restructure just for aesthetics):

```text
src/terrio_processes/
    app.py
    manager.py
    engine.py
    processes/
        info.py
        warp.py              # second milestone
        hillshade.py         # later
    contracts/
        info.py
    storage.py               # only when actual files are served
config/pygeoapi.yml
scripts/                   # only needed compatibility tooling
tests/
docker/Dockerfile
compose.yml
compose.release.yml
pyproject.toml
uv.lock
```

Avoid a generic abstraction framework for one or two operations. Add structure as the second and third processes demonstrate duplication.

## 5. OGC API – Processes 1.0 conformance contract

**Normative source of truth:** [OGC API – Processes – Part 1: Core, version 1.0.0 (18-062r2)](https://docs.ogc.org/is/18-062r2/18-062r2.html), especially §7.10 (process descriptions), §7.11 (execution), §8 (OGC Process Description), and [Annex A (normative) Abstract Test Suite](https://docs.ogc.org/is/18-062r2/18-062r2.html#_abstract_test_suite). Use the [official JSON examples directory](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/) as **examples**, and the corresponding OGC schemas and normative requirements for validation. If this handover, a sample or pygeoapi behavior conflicts with the standard, investigate and document the discrepancy; do not change semantics merely to pass a local test.

**Scope:** The weekend MVP implements one bounded, synchronous, **single-output JSON** process (`terrio-info`) with `outputTransmission: ["value"]`. File-producing processing and reference transmission are **Phase 3**, not part of the immediate assignment. No asynchronous jobs, callback conformance, multipart/multiple-output response, or universal engine abstraction is required. Do not claim overall OGC conformance from a handful of tests: report the conformance classes the service advertises, the tests actually run, and any known limitations.

### 5.1 Discovery and descriptions

- Check `GET /`, `GET /conformance`, `GET /processes`, and `GET /processes/{processID}`. Links, process identifiers, execution URLs, advertised capabilities and actual runtime behavior must agree.
- Describe each process with the OGC Process Description data model (§8): `id`, useful title/description and links; `jobControlOptions`; `outputTransmission`; explicit `inputs` and `outputs` with schemas, types, supported media types and meaningful constraints. Compare a real process description against [ProcessDescription.json](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/ProcessDescription.json) and relevant schema definitions; **do not mistake an example document for a schema**.
- Use `jobControlOptions: ["sync-execute"]` for the bounded processes. For `terrio-info` advertise only `outputTransmission: ["value"]`. Add `"reference"` for a file-producing process **only when the corresponding mode is implemented and tested**. No job resource is required merely because a synchronous execution occurred.
- Verify `/openapi` and `/conformance` reflect what the deployed application supports. Avoid claiming optional Job List, Callback, Dismiss or asynchronous behavior when absent. Preserve upstream output unless actual HTTP/schema tests establish a need for a patch.

### 5.2 Execution request semantics (OGC §7.11.2; Requirements 16–27)

- Accept `POST /processes/{processID}/execution` with a valid OGC execute JSON request (see [Execute.json](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/Execute.json) and the normative `execute.yaml` schema linked in §7.11.2). `inputs` and `outputs` are keyed by their **defined identifiers**, not arbitrary CLI arguments.
- When `response` is omitted, the default is `"raw"`; when `outputs` is omitted, all defined outputs are requested; when an output's `transmissionMode` is omitted, its default is `"value"`. Test these defaults for each supported process as applicable; do not assume a Python return value defines the HTTP shape.
- With `jobControlOptions: ["sync-execute"]`, execution remains synchronous even if the client sends `Prefer: respond-async` (Requirements 25–26). Do not fabricate an asynchronous job or promise unsupported `/jobs/{id}` resources.
- Define input schemas and validate actual input values, including data resolved from references. The standard permits input values both inline and by reference (§7.11.2.2; Requirements 17–24). For the weekend MVP, a documented fixture ID supplied as an **inline string** is an acceptable bounded process input; it is not a substitute for supporting actual external data references in a future interoperable raster process. Do **not** claim full reference-input interoperability until tested.
- For Phase 3, support the standard referenced-input shape, for example `{"href":"https://data.example.org/dem.tif","type":"image/tiff"}`. Resolve and validate it safely (network restrictions, size limits, timeouts and media types); do not accept uncontrolled server file paths. If remote input is beyond the available time, document that limitation rather than misrepresenting a fixture ID as an OGC reference.

### 5.3 Synchronous execution responses (OGC §7.11.4, Requirements 28–32)

The following table is the **HTTP response contract**, not a suggestion to implement every combination during the weekend. Implement and test the combinations the processes actually offer. The currently retained BKN manager uses its own internal `{"id": ..., "value": ...}` result object; **never assume that object is itself the standards-defined external response**.

| Requested response | Transmission mode | Outputs | HTTP | Required external response |
|---|---|---:|---|---|
| `raw` | `value` | One | `200` | Native output with the output's declared media type; no enclosing results document (Requirement 28) |
| `raw` | `reference` | One or more | `204` | Empty body with `Link` header(s) pointing to the results (Requirement 30) |
| `document` | `value` | One or more | `200` | `application/json` results mapping keyed by output ID, containing inline output values (Requirement 32) |
| `document` | `reference` | One or more | `200` | `application/json` results mapping keyed by output ID, containing output references (Requirement 32) |
| `raw` | `value`, multiple outputs | Multiple | `200` | `multipart/related` (Requirement 29); **deferred** |
| `raw` | mixed `value`/`reference` | Multiple | `200` | `multipart/related` (Requirement 31); **deferred** |

For example, a **later** raster process may be requested with a document result and reference output:

```json
{
  "inputs": {
    "source": {
      "href": "https://data.example.org/dem.tif",
      "type": "image/tiff"
    },
    "target_crs": "EPSG:28992"
  },
  "outputs": {
    "result": { "transmissionMode": "reference" }
  },
  "response": "document"
}
```

Illustrative **HTTP 200** JSON result document for that request:

```json
{
  "result": {
    "href": "https://processing.example.org/results/abc123/output.tif",
    "type": "image/tiff"
  }
}
```

The results document is keyed by **`result` (the output ID)**, not wrapped in a made-up top-level `outputs` array. Follow the OGC `results.yaml` schema and [Result.json](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/Result.json). These URLs and bodies are *illustrative*, not proof that a feature is implemented. The correct media type must be grounded in the actual produced file and process description.

For the equivalent `raw` + `reference` request, return **HTTP 204**, an **empty body**, and a `Link` response header referring to the output—not an HTTP 200 JSON object containing a URL. **Do not return** `/tmp/output.tif`, `file:///...`, a Docker-internal hostname, or a URL unreachable from the requesting client. Storage lifetime, publication and clean-up are implementation concerns separate from OGC execution/job management.

### 5.4 Minimal standards test matrix (keep scoped)

**Phase 2 / weekend MVP — required:**

| Test | Expected behavior |
|---|---|
| Process discovery and description | `/processes` and `/processes/terrio-info` expose matching IDs, links, schemas and only genuinely supported capabilities |
| Conformance and OpenAPI | No false async/callback/job claims; endpoint definitions match observed HTTP responses |
| Execute without `response` | Defaults to `raw`; correct single JSON output and `Content-Type`, HTTP `200` |
| Execute with `response: "document"` | HTTP `200`, `application/json`; map keyed by the declared output ID |
| Execute without `outputs` or `transmissionMode` | Requests defined output(s) by `value`; matches explicitly requested behavior |
| Execute with `Prefer: respond-async` | Still runs synchronously; no misleading `201` job response |
| Invalid input / unknown output | Controlled, appropriate 4xx OGC error response without server-internal path/traceback |

**Phase 3 / first GeoTIFF-producing process — required before advertising reference transmission:**

| Test | Expected behavior |
|---|---|
| `document` + `reference` | HTTP `200` JSON result mapping; retrievable output `href`, correct declared media type |
| `raw` + `reference` **if offered** | HTTP `204`, empty body, relevant `Link` header(s) |
| Referenced raster input | Standard input `href` handled securely; retrieved content validated |
| External download test | A separate client/container can HTTP GET the advertised URL and open/inspect the GeoTIFF |
| Defaults and capabilities | Omitted transmission defaults to `value`; behavior is explicitly tested/handled and never silently described as a reference |
| File lifecycle | Result is available for a documented retention period; expired/missing files fail predictably |

Read the normative [Annex A test suite](https://docs.ogc.org/is/18-062r2/18-062r2.html#_abstract_test_suite) when implementing each supported requirement. Add focused automated HTTP tests for these rows rather than trying to implement the entire optional standards surface at once. A passing local contract suite is **not** official OGC certification.

## 6. Implementation plan

### Phase 0 — Baseline and compatibility inventory (do first)

- Read the BKN files listed above, particularly the processor contract, manager, OpenAPI patch, Dockerfile, release Compose and tests.
- Run the repository's current checks **before** editing. Capture actual commands and pass/fail status; note tests dependent on live PDOK separately.
- Record the current externally observable contract: `/processes`, process description, execution `raw` and `document` responses, unsupported `subscriber`, sync-only advertised capabilities, conformance and `/openapi`.
- Inspect the installed and intended Terrio versions in an isolated environment. Verify `terrio.info` against a small local GeoTIFF and note its actual return type; do not assume that every method in current online docs exists unchanged in the pinned wheel.
- Check pygeoapi **0.24.0** (released July 2026) against the project's 0.23.4 workarounds. That release changed process metadata and binary output handling. Use a separate change/test cycle for an upgrade; do **not** blend it invisibly into the initial Terrio integration. If it breaks a required contract, document the problem and keep the last working version until fixed.

**Exit condition:** An inventory of which patches remain needed and a known-good baseline. Do not claim a patch is obsolete without an HTTP test proving equivalent behavior.

### Phase 1 — Separate the new application from BGT

- Work in a new derivative repository/branch as described above.
- Rename application package/imports, Docker image labels, project metadata, pygeoapi resource identifiers and descriptions to `terrio-processes` (or a consistently documented equivalent).
- Preserve license/attribution notices appropriately. Remove BKN-specific public metadata, endpoints, example requests and live-PDOK assumptions from the **new** app.
- Reuse the existing `BaseProcessor`, process-contract and synchronous manager patterns. Generalize the Flask guard only if tests show it is needed; do not preserve it merely because it exists.
- Determine which OpenAPI changes are still needed with the selected pygeoapi version. Prefer upstream-generated OpenAPI over any patched result. If a patch remains, keep it small, version-aware and test-covered; avoid modifying an upstream shell entrypoint with `sed` if a less brittle approach exists.
- Regenerate/lock dependencies. Verify the actual container Python interpreter can `import pygeoapi, terrio`.

**Exit condition:** A clean pygeoapi-based application skeleton with no BGT public API residue and with configuration/startup passing tests.

### Phase 2 — First real process: `terrio-info` (MVP)

Implement exactly one initially: **`terrio-info`**.

- Back it with the **direct Python binding** `terrio.info(source, stats=True)` (or the exact, verified equivalent for the pinned release).
- Use an offline deterministic tiny GeoTIFF fixture, created locally/test-generated; do not rely on PDOK or arbitrary network data for the MVP.
- Accept a **safe, bounded reference** to an input dataset. For the MVP, a configured fixture identifier mapped to a fixed input directory is fine. Avoid accepting user-controlled absolute filesystem paths or remote URLs without a deliberate security design.
- Define explicit `PROCESS_METADATA`, input types, defaults, optional output selection and a JSON output schema matching the actual response. Advertise `jobControlOptions: ["sync-execute"]` and `outputTransmission: ["value"]` only if runtime tests confirm them.
- Preserve the response semantics in **§5.3** for `response: "raw"` and `response: "document"`; validate actual OGC response bodies and HTTP status codes, not just successful Python calls.
- Reject unsupported output IDs, malformed documents, incompatible output formats, callbacks and unsupported execution choices with suitable documented OGC error responses. Confirm which parts upstream handles before adding custom code.
- Expose the process through the regular pygeoapi resource configuration, **without editing upstream pygeoapi**.

**Exit condition:** `GET /processes`, `GET /processes/terrio-info`, `POST /processes/terrio-info/execution` and `/openapi` agree about inputs, supported modes and outputs; the operation actually calls Terrio on local test data.

### Phase 3 — File-producing raster operation (separate milestone)

After the JSON MVP is stable, add **`terrio-warp`**; `terrio-hillshade` is a reasonable next process.

Terrio exposes operations such as:

```python
terrio.warp("input.tif", "output.tif", t_srs="EPSG:28992", resampling="bilinear")
terrio.dem("input.tif", "hillshade", "hillshade.tif", z=2)
```

Treat these as examples; pin and verify the actual supported arguments.

Before exposing file-producing processes:

1. Decide how clients retrieve results, implementing the **§5.3 response contract**: valid OGC output references or true binary-value responses as supported/tested by the selected server. **A path inside the container is not a valid client-download URL.**
2. Add an explicitly writable working/output location compatible with the hardened image, which currently has a read-only root filesystem and just a `64m` `/tmp` tmpfs.
3. Use per-request work directories, safe generated filenames, meaningful media types (e.g. GeoTIFF), and a documented retention/cleanup policy.
4. Test the entire HTTP lifecycle, including a client successfully downloading/opening the output raster, not merely the presence of a success JSON message.
5. Add input-size/time/concurrency limits appropriate for synchronous HTTP. Avoid launching huge unbounded jobs in the API worker.
6. Do not force file output through the old manager's single JSON `id`/`value` formatter if that makes the OGC response wrong. Extend/replace that part based on the tested output transmission model.

Asynchronous execution, persistent queues, extra worker processes/containers, multi-gigabyte datasets, point-cloud processing and S3-backed output are **future architecture options**, not MVP prerequisites.

## 7. Security and deployment guardrails

- Keep non-root execution, minimal capabilities, `no-new-privileges` and (where possible) read-only root filesystem from the release image.
- Do **not** use `sudo apt install` on the developer's Ubuntu host. Add system packages **inside the Dockerfile only if actually required and justified**. Terrio normally ships compiled wheels; verify wheel availability for the chosen platform before assuming Cargo/system packages are needed.
- Respect the Python environment used by the pinned pygeoapi image (`/venv` in the old image); don't accidentally `pip install` into an unused interpreter. Reassess paths when upgrading the base image.
- Default to local/test fixtures, not user-supplied internet URLs. If remote inputs are later enabled: explicitly defend against SSRF, private/loopback/link-local destinations, redirects, DNS resolution changes, oversized responses and unexpected protocols.
- Never pass untrusted strings into `shell=True`, arbitrarily selected executable flags, or filesystem output paths. Treat a user-provided CRS and resampling mode as typed, constrained values.
- Make failures deterministic and avoid leaking stack traces, host paths, credentials or internal addresses to API clients.
- Keep production output storage writable but bounded; define cleanup and observable capacity limits.
- Pin and test dependency versions, especially while Terrio remains early-development software. Keep release-image provenance reproducible.

## 8. Test and acceptance checklist

Use the existing unit / schema / HTTP test discipline **plus the staged normative test matrix in §5.4**. Adapt these checks to `terrio-info`:

- [ ] A deterministic local GeoTIFF can be inspected by Terrio in unit tests, without internet access.
- [ ] The processing adapter has no dependency on pygeoapi.
- [ ] `/processes` contains `terrio-info`; its advertised link resolves to the correct process description.
- [ ] `GET /processes/terrio-info` accurately declares inputs, output media type, `sync-execute`, and supported transmission modes.
- [ ] Valid execution works with `response: raw` and `response: document` (if both are advertised).
- [ ] Actual result JSON matches the declared schema; HTTP headers/content types agree with it.
- [ ] Invalid inputs, unknown fields where disallowed, unsupported output selections, unsupported format and subscriber options return the documented client errors.
- [ ] No unimplemented async/callback conformance claims or OpenAPI response options are advertised.
- [ ] The generated OpenAPI document corresponds to the actual endpoints and behavior (no `/processes/bgt-land-cover-summary` residue).
- [ ] Docker Compose builds and runs; inside the **running** image both `import terrio` and the configured pygeoapi processor import succeed.
- [ ] Release container retains security hardening and a working health check.
- [ ] Lint, tests and documented commands run locally/through containers; skipped tests and external limitations are explicitly listed.
- [ ] Existing BKN repository/history and unrelated projects are untouched.

For later raster-process milestones also require: downloadable/valid GeoTIFF, correct CRS/resolution, safe per-request filenames, sensible failure behavior and storage cleanup.

## 9. What NOT to do

- Do **not** fork or vendor Terrio or pygeoapi now; do **not** patch Rust internals before a demonstrated missing capability.
- Do **not** build a generic `/execute?command=...` shell gateway over Terrio.
- Do **not** implement async job queues just because some raster jobs may eventually need them.
- Do **not** discard known-good contract tests in exchange for a minimal HelloWorld demo.
- Do **not** retain a large hardcoded BGT OpenAPI patch without verifying its continued necessity on pygeoapi 0.24.0.
- Do **not** describe a generated file as available to the client unless a tested external URL or valid raw-output response exists.
- Do **not** silently make incompatible API-contract, dependency-version and execution-model changes in one commit.

## 10. Immediate Codex assignment

**Begin with Phases 0–2 and the Phase 2 tests from §5.4; stop before building `terrio-warp`, reference output transmission or a generalized output-storage system.** Implement the smallest coherent change set that delivers a real `terrio-info` endpoint. You may split the changes into small reviewable commits or patches; do not push, publish, create remote repositories, or overwrite the historical BKN branch without explicit user instruction.

At the end, report:

1. Which BKN components were retained, deleted or refactored, and why.
2. Whether the pygeoapi 0.23.4 → 0.24.0 upgrade was attempted/succeeded, and which compatibility workarounds remain genuinely necessary.
3. Exact versions of pygeoapi and Terrio in the lockfile/image, and whether precompiled Terrio wheels worked.
4. Tests run with pass/fail/skip counts and representative `curl` requests/responses.
5. A concise description of the chosen `terrio-info` input security model.
6. The outstanding design decision for file delivery before implementing `terrio-warp`, including whether and how to provide standards-correct `document`/`reference` output as defined in §5.3.

If an implementation detail contradicts this handover, **inspect the pinned dependency source and prefer observed tests to assumptions**. Document deviations rather than quietly expanding the project scope.

## 11. Good to know

Design for incremental process registration. Each Terrio operation should have its own process implementation and OGC process description. Keep shared infrastructure independent of process-specific output types, output counts and transmission capabilities, as defined by OGC API – Processes Part 1. Implement only the capabilities needed by the currently supported processes. Do not add asynchronous execution, multipart responses or generalized multi-output handling until required.

## 12. Preserve the existing development and validation workflow

The BKN repository already has established linting, security checks, unit tests, integration tests, HTTP contract tests, coverage requirements and CI configuration.

We like these tools and the general workflow around them. At the same time we recognize that the new processes will differ from the BGT proces

Before modifying the project:
1. Identify and document the existing commands for formatting, linting, security analysis, testing and container validation.
2. Preserve the relevant pyproject.toml configurations, uv.lock workflow, pre-commit hooks and GitHub Actions.
3. Adapt existing tests to the new package and processes rather than deleting them wholesale. But feel free to remove tests specifically relating to the BGT process
5. Update documentation so the validation commands remain discoverable.
6. Run all applicable checks and report failures, including checks that cannot run in the current environment.
New processes must receive appropriate unit and HTTP contract tests. Preserve standards-related tests when replacing the original BGT process.

## 13. Python environment

Use the system-wide uv installation for dependency management. Each project must have its own .venv; do not install project dependencies globally.

Do not modify Ubuntu's system Python or install system packages without approval.

Examine the existing Python version constraints and test compatibility before changing them. Prefer using an already available compatible interpreter, but allow uv to manage another Python version when necessary.

Preserve pyproject.toml, uv.lock, and the established testing and linting workflow. Keep the virtual environment out of Git.

All Python commands, tests and linters must run through uv run.

Don't feel like you have to use Python 3.12 just because your .python-version or toml says so. We think newer versions should also be compatible.

## 14. Clean-up

This is not a Breinstein project, and the only contributer in this project is Gouwe-Gozer. References to the company, a spike for a testbed and to the other contributors can be removed.

## 15. Reference links

- BKN source: https://github.com/Gouwe-Gozer/bkn-terrain-processes
- pygeoapi upstream: https://github.com/geopython/pygeoapi
- pygeoapi plugins: https://docs.pygeoapi.io/en/stable/plugins.html
- pygeoapi Docker: https://docs.pygeoapi.io/en/stable/docker.html
- pygeoapi 0.24.0 release notes: https://github.com/geopython/pygeoapi/releases/tag/0.24.0
- Terrio upstream: https://github.com/opengeos/terrio
- Terrio Python bindings and operation examples: https://terrio.opengeos.org/python/
- OGC API – Processes Part 1: Core, **normative text**: https://docs.ogc.org/is/18-062r2/18-062r2.html
- OGC official JSON **examples** (not schemas): https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/
- OGC process description example: https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/ProcessDescription.json
- OGC execute request example: https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/Execute.json
- OGC results example: https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/Result.json
- OGC normative abstract test suite: https://docs.ogc.org/is/18-062r2/18-062r2.html#_abstract_test_suite
- OGC standards overview: https://www.ogc.org/standard/ogcapi-processes/
