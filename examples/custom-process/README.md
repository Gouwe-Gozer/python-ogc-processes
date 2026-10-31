# A custom Python process

This example exposes an ordinary text-statistics function through the existing
API and durable worker. It uses only the service's existing dependencies. It is
**not enabled in the default deployment**.

| File | Purpose |
| --- | --- |
| `custom_processes/operation.py` | Your Python function, with no API imports |
| `custom_processes/contract.py` | Explicit input/output schemas and process metadata |
| `custom_processes/processor.py` | A direct pygeoapi `BaseProcessor` subclass |
| `process.yml` | Explicit registration to add under `resources` |
| `request.json` | A complete execution request |
| `Dockerfile`, `compose.yml` | The same custom image/configuration for API and worker |

## Run it

Run these commands **from the repository root**, with Docker Compose and uv
installed. Choose a free port; this separate project does not replace your
ordinary deployment.

```bash
uv sync --locked --all-groups
mkdir -p runtime-data/custom-process
uv run python - <<'PY'
from pathlib import Path
import yaml
config = yaml.safe_load(Path("config/pygeoapi.yml").read_text())
config["resources"].update(yaml.safe_load(Path("examples/custom-process/process.yml").read_text()))
Path("runtime-data/custom-process/pygeoapi.yml").write_text(yaml.safe_dump(config, sort_keys=False))
PY

docker build -f docker/Dockerfile -t raster-processes:0.1.0 .
API_PORT=5002 PYGEOAPI_SERVER_URL=http://localhost:5002 \
  docker compose -p raster-custom-example \
  -f compose.release.yml -f examples/custom-process/compose.yml \
  up --build --wait
```

The copied configuration preserves the five raster processes and adds
`text-statistics`. The base image and example Dockerfile are built separately;
the latter copies only the contributor's package into the existing Python path.
Both services use that derived image. The example retains the base image's
non-root user and all Compose limits/security settings.

## Discover and execute

```bash
curl --fail-with-body 'http://localhost:5002/processes/text-statistics?f=json'
curl --fail-with-body http://localhost:5002/processes/text-statistics/execution \
  -H 'Content-Type: application/json' \
  --data-binary @examples/custom-process/request.json
```

The synchronous result is HTTP 200 with
`{"statistics":{"value":{"characters":22,"words":4}}}`.
Set `"response": "raw"` to receive just `{"characters":22,"words":4}`.
The input also accepts qualified JSON values and controlled HTTPS references to
JSON strings, through existing input handling. Reference **output** transmission
is intentionally unsupported by this example.

To submit asynchronously:

```bash
curl --fail-with-body -i http://localhost:5002/processes/text-statistics/execution \
  -H 'Content-Type: application/json' -H 'Prefer: respond-async' \
  --data-binary @examples/custom-process/request.json
# Copy the Location header from the HTTP 201 response, then substitute JOB_ID:
curl --fail-with-body http://localhost:5002/jobs/JOB_ID
curl --fail-with-body http://localhost:5002/jobs/JOB_ID/results
```

Poll until `successful` or `failed`. Results return 404 / `ResultNotReady` while
pending; input validation happens in the worker, so an invalid async input is
accepted first and later produces a failed job with the original error status.
See [async execution](../../docs/asynchronous-execution.md) for limits/lifecycle.

Open <http://localhost:5002/openapi?f=html> and locate `text-statistics`.
Try `{"inputs":{"text":42}}`: sync returns 400 / `InvalidParameterValue`;
async returns that error from the job's results. Adding configuration alone does
not implement or enforce schemas; the processor owns semantic validation.

## Check and stop

```bash
uv run pytest tests/test_custom_process.py -v
GEO_TEST_ASYNC_CONTAINERS=1 uv run pytest tests/test_async_containers.py -k custom_process -v
# Stop this example only; its named job/result volumes remain:
API_PORT=5002 PYGEOAPI_SERVER_URL=http://localhost:5002 \
  docker compose -p raster-custom-example \
  -f compose.release.yml -f examples/custom-process/compose.yml down
```

Container tests build both images, reuse this Compose override, and verify
actual discovery, OpenAPI, synchronous/async results and typed failures. They
create/remove only their unique `raster-async-test-*` resources. See
[adding a process](../../docs/adding-a-process.md) to adapt the example to your code,
install dependencies and deploy changes to both services.
