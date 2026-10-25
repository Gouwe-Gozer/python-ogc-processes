# Processing your own rasters

All five raster processes accept a self-contained GeoTIFF through an
HTTPS reference, inline base64 string or qualified inline base64 value. The
bundled demo file remains a test fixture; `demo-dem` is not an API input.
Each execution acquires its own input and discards the staged file afterward.
There is no reusable input ID or separate upload endpoint. Outputs retain their
independent [24-hour lifecycle](results.md).

## Process a local file

With the service running, inspect and reproject your own file in one command:

```bash
uv run python scripts/process_raster.py my-dem.tif --output my-dem-wgs84.tif \
  --base-url http://localhost:5001 --target-crs EPSG:4326
```

This user-facing example uses ordinary inline base64 for `raster-info`, then
`raster-warp` with document/reference output, and downloads that reference.
It prints source dimensions/band count and the saved filename. Choose one of
the three supported target CRSs and optionally `--resampling nearest` (default
`bilinear`). Include any proxy prefix in `--base-url`, matching the service's
canonical public URL. No extra client package or upload endpoint is needed.

The input must be a self-contained GeoTIFF within the service limits. The
destination's parent directory must exist; an existing file is never overwritten.
Incomplete/failed downloads are discarded. API errors are printed with their
HTTP status and detail, and the command exits nonzero. This small synchronous
client does not automatically retry busy/full responses.

To try it with the test fixture, submit that file as ordinary raster data:

```bash
mkdir -p runtime-data
uv run python scripts/process_raster.py src/geo_processes/data/demo-dem.tif --output runtime-data/demo-wgs84.tif
```

Use `uv run python scripts/process_raster.py --help` for options. The lower-level
request examples below expose the same wire contract. `smoke_inputs.py` remains
the developer check for all response/transmission modes.

## Submit a local file inline

Create a request from your own `my-dem.tif`:

```bash
uv run python - <<'PY'
import base64
import json
from pathlib import Path

source = Path("my-dem.tif")
payload = {
    "inputs": {
        "source": {
            "value": base64.b64encode(source.read_bytes()).decode("ascii"),
            "mediaType": "image/tiff",
            "encoding": "base64",
        },
        "target_crs": "EPSG:4326",
    }
}
Path("runtime-data").mkdir(exist_ok=True)
Path("runtime-data/my-raster-request.json").write_text(json.dumps(payload))
PY

curl --fail-with-body http://localhost:5001/processes/raster-warp/execution \
  -H 'Content-Type: application/json' \
  --data-binary @runtime-data/my-raster-request.json \
  --output runtime-data/my-warped.tif
```

The default response is HTTP 200 with GeoTIFF bytes. For info, submit the same
`source` to `/processes/raster-info/execution` and omit `target_crs`. For an
output URL, add `"outputs":{"result":{"transmissionMode":"reference"}},"response":"document"`.
All [four warp response modes](results.md#http-contract) remain supported.

For developer checks across all output modes, see the
[input smoke workflow](development.md#container-and-integration-checks).

## Submit an HTTPS reference

Replace the example URL with a downloadable GeoTIFF:

```json
{
  "inputs": {
    "source": {"href": "https://data.example.org/my-dem.tif", "type": "image/tiff"},
    "target_crs": "EPSG:4326"
  },
  "outputs": {"result": {"transmissionMode": "reference"}},
  "response": "document"
}
```

Reference `type` is optional; ordinary `rel`, `title` and `hreflang` string
metadata is accepted and does not change fetching. Qualified raster objects
require `mediaType` and `encoding`.
An unwrapped base64 string is also accepted; its GeoTIFF media type is supplied
by the process description. Qualified inline objects retain their explicit
`mediaType` and `encoding`, as in the local-file example above.
Accepted types are `image/tiff`, `application/tiff` and
`application/tiff; application=geotiff`. The actual file is always validated.
The origin must return a complete HTTP 200 response without HTTP content
compression. Chunked transfer and TIFF's internal compression are supported.
The entire file is downloaded; remote COG window reads are not implemented.

A rejected upstream status is reported separately, for example
`source returned HTTP 404; expected HTTP 200 (check the reference URL)`.
Unsupported HTTP compression instead reports
`source uses unsupported HTTP Content-Encoding; expected identity`.
Both are input errors (our execution returns HTTP 400). Upstream response bodies,
headers, URL/query details and reason phrases are not copied into the error.

URLs must be ASCII HTTPS URIs on port 443, without userinfo credentials,
fragments, alternate ports or backslashes. Percent-encode non-ASCII paths and
queries. Signed query URLs work; arbitrary headers and cookies are not sent.

Every destination and redirect is checked. Private, loopback, link-local,
multicast, reserved and IP translation addresses are blocked, including mixed
public/private DNS answers. Connections use a validated IP with verified TLS
and the original SNI/Host, avoiding a second hostname lookup. Ambient proxy
variables are ignored. There are at most three redirects, each rechecked.
The first validated address is used; address retry is not implemented.

`GEO_INPUT_ALLOWED_HOSTS` can restrict destinations to comma-separated exact
hostnames. Empty allows any otherwise permitted public HTTPS host. Redirect
hosts must also be listed. An allowlist never bypasses public-address checks;
there is no private-address or TLS-disable switch.

## Chain raster operations

A warp or reclassification result can be supplied directly as the next raster
input when its download URL satisfies the same public HTTPS policy. After a
document/reference execution, the returned `result` object already has the
accepted `href`/`type` shape. For example, create the next `raster-info` request:

```python
next_request = {"inputs": {"source": first_response["result"]}, "response": "document"}
```

The URL is fetched normally and its TIFF is validated again; there is no
special internal-artifact lookup or bypass for service-owned hosts. Requirements:

- Set `PYGEOAPI_SERVER_URL` to the external HTTPS base URL, including any proxy
  prefix; see [TLS termination and routing](release-image.md#reverse-proxy-and-tls-termination).
- From inside the API container, **all** DNS answers for the public hostname
  must be public unicast addresses. Split DNS returning a private address is
  rejected. The selected public address must route back through the proxy on
  port 443, with a certificate trusted by the container and matching the hostname.
  Public IPv4/IPv6 reachability and any NAT/hairpin route need live verification;
  the resolver uses the first validated address without address retry.
- If `GEO_INPUT_ALLOWED_HOSTS` is set, include the public service hostname and
  any redirect host. Redirects are checked again. Ambient proxy settings are
  ignored; private backends are never direct input destinations.
- Result downloads must work without extra authentication headers or cookies
  and return HTTP 200 without content compression. A proxy must honor
  `Accept-Encoding: identity`. TLS may terminate there; the private proxy-to-API
  hop does not bypass destination checks on the public input URL.
- Keep an API worker available for the nested download. The default two sync
  workers can serve one chaining execution plus its result GET. Two simultaneous
  self-fetching executions can occupy both workers and time out waiting for
  their downloads. A single sync worker cannot serve its own nested request.
  Control chaining concurrency and verify capacity on the deployment; no worker
  or resource limits are changed automatically.
- Start the next operation before the result expires. Byte/sample limits still
  apply; GeoJSON outputs cannot be used as raster inputs.

Local `http://localhost:5001/results/...` references remain unsuitable for
server-side chaining. Download the result in the client and submit it inline
for local testing. Local TLS regressions cover reference reuse and private-DNS
rejection; they do not establish public DNS, proxy or loaded-deployment behavior.

## Scalar input references

`raster-warp` accepts `target_crs` and `resampling` as literal strings, qualified
values such as `{"value":"EPSG:4326"}`, or controlled HTTPS references:

```json
{
  "target_crs": {"href": "https://data.example.org/target.json", "type": "application/json"},
  "resampling": {"href": "https://data.example.org/resampling.txt", "type": "text/plain"}
}
```

These are members of the execution `inputs` object alongside `source`. A JSON
resource contains the literal string, for example `"EPSG:4326"`; a plain-text
resource contains `nearest` or `bilinear`. Bodies are UTF-8, limited to **4096
bytes** per scalar; surrounding plain-text whitespace is removed. `type` is
optional when the response identifies JSON/text. If supplied, it must match the
response media type. Qualified inline values may also specify a supported
`mediaType` (`application/json` or `text/plain`).

Resolution uses the same public-address, TLS, redirect, allowlist, timeout and
temporary-slot controls as raster input. Each reference has its own fetch
deadline; the Gunicorn worker timeout remains the outer execution limit. Fetched
values are checked against the same choices as literals. Nested reference
objects are not followed. Invalid values/media/JSON return 400; oversized scalar
bodies return 413. Scalar and raster workspaces are removed after use.

The process description still advertises string enums: wire alternatives belong
to execution, not the native value schema. These rules are independent of sync
or async execution.

## Limits, validation and cleanup

| Limit | Current value |
| --- | --- |
| JSON execution request | 24 MiB, allowing base64 overhead |
| Decoded/downloaded raster | 16 MiB |
| Samples including bands | 1,048,576 |
| Decoded raster block | 16 MiB |
| GDAL block cache per worker | 16 MiB |
| URL length | 4,096 characters |
| Active staged inputs | Two across workers sharing the input directory |
| Socket operation timeout | Three seconds, shortened to remaining budget |
| Fetch deadline | Ten seconds across redirects and reads |

The deadline interrupts slow headers and trickling bodies. DNS uses the OS
resolver and cannot itself be interrupted by the socket deadline; elapsed DNS
time is deducted afterward. The release's 30-second worker timeout is the outer
limit. Increase operating limits only after measuring representative workloads.

`GEO_INPUT_TMPDIR` defaults locally to `runtime-data/inputs`; both Compose
configurations use `/tmp/geo-inputs`. Only release Compose bounds `/tmp` with a
64 MiB tmpfs; development Compose does not set that mount or memory limit.
Two file locks protect private workspaces. Completion and handled failures remove
inputs. A killed worker
releases its lock, and the next use of that slot removes the abandoned input.
Idle abandoned files remain until slot reuse or storage removal; release tmpfs
is recreated on container restart. They are bounded by the two slots, separately
from the persistent result volume and its expiry.

Only the GTiff driver opens staged files. VRTs, archives, subdatasets and complex
rasters are unsupported. Sidecars/PAM are disabled and georeferencing comes from
the TIFF itself. PROJ grid-network access is disabled at application startup.
Rasterio receives a private local path, never the input URL. Metadata, dimensions,
block bounds and all band data are validated before processing. Info/reclassify
permit a missing CRS; warp/sample/polygonize require one.

The new operations also accept bounded JSON parameters: GeoJSON points, class
intervals, band and connectivity. They reuse this resolver's HTTPS transport,
host policy and staging. Each JSON parameter is limited to 256 KiB. Object
values use an OGC qualified `value` wrapper; see
[operation contracts and examples](raster-operations.md).

Malformed inputs, disallowed URLs, failed downloads and unsupported rasters
return JSON 400. Oversized bodies or raster bytes return 413; busy input slots
return 503. Internal storage/processing failures return sanitized 500 responses.

## OGC scope and deployment

Process descriptions advertise one binary GeoTIFF value using `type: string`,
`format: byte`, `contentEncoding: binary` and `contentMediaType: image/tiff`.
Accepted TIFF media-type aliases describe the same format. Reference and inline
transport are handled by the execution contract; they do not need separate
alternatives in the public value schema.

See the [OGC review guide](validation.md#ogc-review-guide) and its official JSON
examples for Requirements 18, 22, 24 and 49–51. Discovery/reference documents
are checked against official schemas; inline binary values also require
application schemas and TIFF decoding because of the
[published schema overlap](validation.md#published-binary-schema-limitation).

The [conformance gaps](validation.md#conformance-claims-and-gaps) remain explicit.
File-picker/URL controls are client UX choices; service schema validation does
not verify the external client's behavior. See [client interoperability](client-interoperability.md).

## Milestone validation

Dated user-input checks and measured workload observations are consolidated in
[recorded validation](validation.md#recorded-checks). Run the
[development checks](development.md) for current evidence.
