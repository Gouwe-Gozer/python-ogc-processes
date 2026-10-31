# Adding a Python process

A process is an ordinary Python function plus a direct pygeoapi `BaseProcessor`
subclass and explicit configuration. No API routes, worker dispatch code,
registry or automatic discovery need to change. The
[working custom-process example](../examples/custom-process/README.md) walks
through building and running independent code, including durable async execution.
The bundled raster operations are examples of this integration, not a requirement
for contributed functions. Check [resource configuration](release-image.md#resource-configuration)
before choosing workload size and duration.

## Choose an integration path

| Path | Files and installation |
| --- | --- |
| In this repository | Put the function (or a call to an existing library) in `src/geo_processes/operations/<name>.py`, a direct wrapper in `processes/<name>.py`, and metadata/schemas in `contracts/<name>.py`. Paths after the first are relative to `src/geo_processes/`. Register it in `config/pygeoapi.yml` and add focused tests. Existing source mounts/image copies include these modules. |
| External Python package | Keep the function in its existing package. Put its wrapper here or in that package, install the package for both services and register the wrapper's dotted name. A locked registry wheel uses the existing Docker build; unpackaged source can use the example's derived image. |

Keep existing processing code unchanged where practical. A wrapper adapts JSON
inputs and serializable results; live datasets, CLI interaction and API-process
global state are not execution inputs. Add dependencies to `pyproject.toml` and
`uv.lock` when needed. Do not change API routes, the manager or worker dispatch
for an ordinary integration. The three-file layout is a convention; OGC specifies
wire contracts, while `BaseProcessor` and dotted registration are pygeoapi interfaces.
The result/OpenAPI hooks below are repository-specific, not OGC Python interfaces.

## 1. Write your function

Keep processing code independent of HTTP and job management. For example,
[`operation.py`](../examples/custom-process/custom_processes/operation.py) accepts
a string and returns a dictionary of counts. Replace it with your own function;
it need not be a Rasterio operation. Do not import the API or a job manager.

Choose explicit inputs, output identifiers, units/CRSs where relevant, defaults,
formats and resource bounds. Open datasets and temporary files inside each
execution, close them with context managers, and avoid mutable global state.
Do not rely on API-process memory: async runs in a fresh worker child per job.
Keep imports and processor constructors cheap: discovery, OpenAPI generation
and async submission instantiate processors too. Load large models/data during
execution rather than fetching or allocating them for metadata discovery.
There is no persistent in-memory model cache across async jobs.

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
- Reuse `validate_inputs`, `resolve_json` and `output_transmission` where applicable.
  `resolve_source` is specifically a bounded GeoTIFF resolver; `processing_errors`
  includes Rasterio error handling. Non-raster functions need not use them.
  Reuse bounded HTTPS transport and typed errors for supported references;
  do not implement unchecked URL fetching to accept a new input format.
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
All output values must be representable by the durable result serializer.
JSON uses pygeoapi's existing conversions, including date/time to strings,
Decimal to numbers and NumPy integers to integers. Return finite JSON values;
async persistence rejects NaN/Infinity. Native text/bytes preserve their media
type and body. Live datasets, generators and arbitrary custom objects are not
supported. Test actual HTTP results instead of assuming Python type identity
survives JSON conversion.

Set initial `jobControlOptions` to `sync-execute`. pygeoapi adds `async-execute`
when the configured manager supports it. No processor-specific async method,
queue, database connection or manager import is needed. In the synchronous opt-out,
`Prefer: respond-async` continues to execute synchronously. Worker validation is
performed after acceptance; invalid async jobs expose their errors at `/jobs/{jobID}/results`.

## 3. Install and register explicitly

Add your importable package to both runtimes. The unpackaged-source example
copies `custom_processes` into `/pygeoapi`, which the base image already puts on `PYTHONPATH`. In-repository
modules and locked registry packages do not require that extra copy or a derived
image: the existing build copies `geo_processes` and installs production packages
into `/venv`. Both services use that same image.
For host-only development with the example, use
`PYTHONPATH=examples/custom-process uv run ...`; that does **not** install code
inside Docker or make it available to a separate worker automatically.

The example needs no new dependencies. Processes share the [same Python environment](development.md):
there are no per-process virtual environments or independent version constraints.
An external dependency must be compatible with the existing lock and supported
Python version. GPU/model-runtime compatibility has not been established by the
text example. For a real dependency:

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

For process-specific options such as a model path, add fields under `processor`
and read them explicitly from `processor_def` in your wrapper. These are options
your code implements, not automatic CPU/memory/timeout policies. Supply model/data
mounts to both services when both execution modes need them; never store secrets
in metadata or execution examples.

This is pygeoapi's existing explicit registration, not a new plugin registry.
Keep the resource ID and metadata ID consistent. A Python import alone does not
publish a process. The [example quickstart](../examples/custom-process/README.md#run-it)
creates a disposable copy of the canonical configuration and merges this exact
stanza; production integrations can edit their maintained configuration directly.

Use identical code, dependencies, configuration and required data in **both API
and worker**. Rebuild/recreate both after image changes; restart both after
bind-mounted code/configuration changes. The worker reads configuration at startup
and spawns fresh children. Installing a module only in the API is insufficient.
For a portable release, follow the example's [packaged deployment](../examples/custom-process/README.md#package-for-deployment).
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

Use [test_custom_process.py](../tests/test_custom_process.py) as a small function,
processor, error and contract test template. The `custom_process` HTTP tests in
[test_async_containers.py](../tests/test_async_containers.py) verify the installed
image/configuration through the real worker. Adapt these focused tests; do not
copy worker internals or add a parallel test framework.

Generic discovery/pagination tests exercise the configured registry and an added
custom process. Explicit bundled-process checks remain separate; retain them when
adding operations. For code outside the checked `src/`, `tests/`, `scripts/` and
custom-example paths, include it in your own package's quality checks.

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
Keep current guidance here and in operation docs.
Adding a process does not establish OGC certification or change conformance baselines.

## Raster and file processes

Use the bundled `raster-info` wrapper for a JSON result example and `raster-warp`
for file delivery; the module layout follows the integration paths above.

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
