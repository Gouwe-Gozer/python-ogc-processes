# Adding a Python process

A process is an ordinary Python function plus a direct pygeoapi `BaseProcessor`
subclass and explicit configuration. No API routes, worker dispatch code,
registry or automatic discovery need to change. The
[working custom-process example](../examples/custom-process/README.md) walks
through building and running independent code, including durable async execution.
The default deployment continues to expose only the five raster operations.

## 1. Write your function

Keep processing code independent of HTTP and job management. For example,
[`operation.py`](../examples/custom-process/custom_processes/operation.py) accepts
a string and returns a dictionary of counts. Replace it with your own function;
it need not be a Rasterio operation. Do not import the API or a job manager.

Choose explicit inputs, output identifiers, units/CRSs where relevant, defaults,
formats and resource bounds. Open datasets and temporary files inside each
execution, close them with context managers, and avoid mutable global state.
Do not rely on API-process memory: async runs in a separate worker child process.

## 2. Define the contract and wrapper

Follow the example's
[`contract.py`](../examples/custom-process/custom_processes/contract.py) and
[`processor.py`](../examples/custom-process/custom_processes/processor.py):

- Describe input **values** and output values using ordinary OGC Process Description
  metadata/JSON schemas, including titles, occurrence counts, versions and media
  types. Give each output a stable identifier. No schema system is added here.
- Inherit directly from `pygeoapi.process.base.BaseProcessor`; pass a **deep copy**
  of metadata to its constructor. The pinned OpenAPI generator mutates metadata.
- Implement `execute(self, data, outputs=None)` to validate/resolve inputs, call
  your function and return `(media_type, value)`. Metadata schemas do not
  automatically validate runtime inputs. Set `supports_outputs = True` when
  accepting output selection/options; otherwise pygeoapi ignores those options.
- Reuse `validate_inputs`, `resolve_json`/`resolve_source`, `processing_errors`
  and `output_transmission` where applicable. These retain bounded HTTPS
  transport and existing typed errors; never fetch arbitrary input URLs yourself.
  The example accepts bare/qualified JSON strings or HTTPS JSON references and
  bounds text to 4096 characters. It rejects reference outputs.
- Use `InvalidExecutionRequestError` for invalid parameters. Unexpected exceptions
  are sanitized by the shared manager. See the [error catalogue](errors.md);
  do not expose internal paths or exception strings.

Two small, existing **service-specific hooks** complete this repository's contract;
they are not extra pygeoapi base classes:

| Hook | Responsibility |
| --- | --- |
| `format_result(value, response)` | Preserve raw output or map output identifiers to OGC document values, e.g. `{"statistics": {"value": value}}`. Required here for document responses; without it only raw execution is supported. |
| `openapi_execution()` | Provide precise `requestBody` and successful `responses` schemas. Shared generation adds standard errors, async 201 responses and Prefer documentation. Without it, upstream's generic execution documentation remains. |

The example uses these hooks for one JSON output delivered by value. Return JSON
values rather than pre-encoding them; shared HTTP handling preserves JSON/HTML
safety. Native text/bytes and file delivery use the existing response helpers.
All output values must be representable by the durable result serializer
(JSON values, text or bytes; not live datasets, generators or custom objects).

Set initial `jobControlOptions` to `sync-execute`. pygeoapi adds `async-execute`
when the configured manager supports it. No processor-specific async method,
queue, database connection or manager import is needed. In the synchronous opt-out,
`Prefer: respond-async` continues to execute synchronously. Worker validation is
performed after acceptance; invalid async jobs expose their errors at `/jobs/{jobID}/results`.

## 3. Install and register explicitly

Add your importable package to both runtimes. The example copies `custom_processes`
into `/pygeoapi`, which the base image already puts on `PYTHONPATH`. A separately
packaged library can instead be installed into `/venv` during image construction.
For host-only development with the example, use
`PYTHONPATH=examples/custom-process uv run ...`; that does **not** install code
inside Docker or make it available to a separate worker automatically.

The example needs no new dependencies. For a real dependency:

1. Add a pinned dependency with `uv add 'PACKAGE==VERSION'`; retain intentional
   `pyproject.toml` and `uv.lock` changes together.
2. Rebuild the base image used by **both API and worker**. Its Docker build reads
   the same manifest/lock and installs production dependencies automatically;
   no Docker dependency list needs updating. Rebuild any derived custom-process
   image afterward, as shown in the example quickstart. Development groups are
   not installed into the application image. Preserve dependency licence notices.
   The current build expects registry wheels; dependencies requiring source
   compilation or local path packages need deliberate build inputs/review.

Under `resources` in your pygeoapi configuration, register the dotted class name:

```yaml
text-statistics:
  type: process
  processor:
    name: custom_processes.processor.TextStatisticsProcessor
```

This is pygeoapi's existing explicit registration, not a new plugin registry.
Keep the resource ID and metadata ID consistent. A Python import alone does not
publish a process. The [example quickstart](../examples/custom-process/README.md#run-it)
creates a disposable copy of the canonical configuration and merges this exact
stanza; production integrations can edit their maintained configuration directly.

Use identical code, dependencies, configuration and required data in **both API
and worker**. Rebuild/recreate both after image changes; restart both after
bind-mounted code/configuration changes. The worker reads configuration at startup
and spawns fresh children. Installing a module only in the API is insufficient.
The example Compose override shares one image and config; normal source mounts
cover only `geo_processes`, so an external development package needs an explicit
mount in both services. Deploy trusted code; there are no runtime code uploads.

## 4. Verify through HTTP

The [quickstart](../examples/custom-process/README.md#discover-and-execute) supplies
actual discovery, sync and async curl requests. Confirm:

- `/processes` lists the resource and `/processes/{id}` describes its real inputs,
  outputs, transmission modes and execution modes.
- Synchronous execution, raw/document choices and typed invalid-input responses
  agree with the metadata and OpenAPI schemas.
- `Prefer: respond-async` returns 201/Location; the worker completes the job;
  status and result retrieval agree with synchronous output. Check failed jobs too.
- `/openapi?f=json` and the interactive HTML docs contain the new operation. The
  entrypoint regenerates OpenAPI on startup; a standalone host generator also
  needs your package on its Python import path.

Run `make test` plus the example's focused/container commands. The example's Python
code is included in normal Ruff/Bandit checks; container tests are explicitly
opt-in and reuse the existing lifecycle fixture. For your own operation, add small
integration tests covering correct parameters/results, each advertised mode and
controlled errors. Use the official offline schemas via `validate_official()`;
examples are illustrative documents, not validation schemas.

Review [OGC guidance](validation.md#ogc-review-guide), the
[Part 1 standard](https://docs.ogc.org/is/18-062r2/18-062r2.html), official
[ProcessDescription.json](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/ProcessDescription.json)
and [Execute.json](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/Execute.json),
and pygeoapi's [custom-process guidance](https://docs.pygeoapi.io/en/stable/plugins.html).
Keep current guidance here and in operation docs; `CODEX_HANDOVER.md` is historical.
Adding a process does not establish OGC certification or change conformance baselines.

## Raster and file processes

For operations maintained inside this project, keep the existing layout:
`contracts/<operation>.py` for metadata/schemas, a plain function in an operation
module, and `processes/<operation>.py` for the direct processor wrapper.
Use `raster-info` for JSON results and `raster-warp` for file delivery.

Reuse `contracts/sources.py` for GeoTIFF value/wire conventions and
`inputs.resolve_source()` for acquisition/validation/cleanup. Set `require_crs=True`
when georeferencing is needed. Account for bands, decoded blocks and simultaneous
inputs/outputs, including compressed TIFFs; keep existing limits. Do not pass
user URLs or arbitrary driver/GDAL options directly to Rasterio.

For TIFF/GeoJSON results, reuse `ResultStore.publish()`, `delivery.FileOutput` and
`format_file()` with their quotas/lifetime. Declare `result_extension` for OpenAPI
download registration and use `ProcessResponse` when native bytes/headers/204s
are required. New file types require deliberate allowlist/download changes;
JSON-by-value processes need no file-storage changes.
Test small raster outputs for pixels, CRS, transform, masks/nodata and bounds;
download reference results independently. See [inputs](inputs.md),
[results](results.md), [architecture](architecture.md) and [development](development.md).
