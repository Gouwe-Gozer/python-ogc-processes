# Processing your own rasters

Both `raster-info` and `raster-warp` accept a self-contained GeoTIFF through an
HTTPS reference, inline base64 string or qualified inline base64 value. The
bundled demo file remains a test fixture; `demo-dem` is not an API input.
Each execution acquires its own input and discards the staged file afterward.
There is no reusable input ID or separate upload endpoint. Outputs retain their
independent [24-hour lifecycle](results.md).

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

This check automates info, all four warp modes and HTTP downloads for your file:

```bash
uv run python scripts/smoke_inputs.py --input-raster my-dem.tif --base-url http://localhost:5001
```

Without `--input-raster`, it generates a two-band 64 by 48 UInt16 raster with
nodata, independently of the service's demo fixture.

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

Reference `type` is optional; qualified inline objects require `mediaType` and `encoding`.
An unwrapped base64 string is also accepted; its GeoTIFF media type is supplied
by the process description. Qualified inline objects retain their explicit
`mediaType` and `encoding`, as in the local-file example above.
Accepted types are `image/tiff`, `application/tiff` and
`application/tiff; application=geotiff`. The actual file is always validated.
The origin must return a complete HTTP 200 response without HTTP content
compression. Chunked transfer and TIFF's internal compression are supported.
The entire file is downloaded; remote COG window reads are not implemented.

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

`GEO_INPUT_TMPDIR` defaults locally to `runtime-data/inputs`; Compose fixes it to
`/tmp/geo-inputs` in the existing 64 MiB tmpfs. Two file locks protect private
workspaces. Completion and handled failures remove inputs. A killed worker
releases its lock, and the next use of that slot removes the abandoned input.
Idle abandoned files last until slot reuse or tmpfs recreation, bounded by the
two slots. This is separate from the persistent result volume and its expiry.

Only the GTiff driver opens staged files. VRTs, archives, subdatasets and complex
rasters are unsupported. Sidecars/PAM are disabled and georeferencing comes from
the TIFF itself. PROJ grid-network access is disabled at application startup.
Rasterio receives a private local path, never the input URL. Metadata, dimensions,
block bounds and all band data are validated before processing. Info supports
missing CRS; warp requires a CRS.

Malformed inputs, disallowed URLs, failed downloads and unsupported rasters
return JSON 400. Oversized bodies or raster bytes return 413; busy input slots
return 503. Internal storage/processing failures return sanitized 500 responses.

## OGC scope and deployment

References use an OGC link; binary values use qualified
`value`/`mediaType`/`encoding` or a direct base64 string. Process metadata describes
one binary GeoTIFF value with `type: string`, `format: byte`,
`contentEncoding: binary` and `contentMediaType: image/tiff`. The other accepted
TIFF media types are aliases of this same format. No `anyOf` or `oneOf` is needed
in that value schema to select transport. Execution schemas separately describe
the supported request forms. See the
[OGC review guide](validation.md#ogc-review-guide), Core requirements 18, 22 and
24, and [official schema snapshot](../tests/schemas/ogc-processes-1.0/README.md).

Reference requests are checked against official schemas. The published binary
schema overlap also affects inline inputs, so those use application schemas
and real TIFF decoding; see the [limitation](validation.md#published-binary-schema-limitation).
Scalar CRS/resampling references, multipart outputs and Core job resources
remain unsupported. Complete OGC conformance or certification is not claimed.

The input-description review follows [18-062r2](https://docs.ogc.org/is/18-062r2/18-062r2.html),
requirements 18 and 22 (reference/inline delivery), 49–50 (value schemas and binary
values), and 51 (`oneOf` for actual mixed-type inputs). The official
[ProcessDescription.json](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/ProcessDescription.json)
describes binary images with `contentEncoding` and `contentMediaType`; its
[Execute.json](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/Execute.json)
shows link and qualified-base64 transport. These examples guide interpretation;
advertised descriptions are validated against the unchanged normative
`process.yaml`/`schema.yaml` snapshot. A local file picker remains a client UI
choice; this schema change does not by itself verify a particular client.

This remains a bounded synchronous pilot. Authentication, TLS termination,
egress firewall policy, rate limits and private-data handling are deployment
decisions. Output URLs remain accessible to anyone who knows them until expiry.

## Milestone validation

The input-description review on `feat/user-raster-inputs` passes **311 tests**
with **95.80% coverage**. Both advertised raster descriptions validate against
the normative OGC schemas, while HTTP tests cover reference, direct base64 and
qualified base64 delivery and rejection of the retired demo identifier.
The rebuilt release also passes discovery, all warp modes, direct-base64 and
executable-example checks, plus the independent-container user-raster smoke test.

The initial user-input checkpoint (`eafb167`), checked on **2026-10-24**, was
based on the merged Rasterio pivot (`main` at `88a83a2`) and passed **293 tests**
with **95.78% coverage**. Ruff format/lint, Bandit, public/integration configuration
and OpenAPI validation, and all Compose configurations pass. The only pytest
warning is the existing upstream Pydantic configuration deprecation.

The release checks submit an independent two-band 64 by 48 UInt16 raster through
Gunicorn from host and separate-container clients. Both info representations,
all four warp output modes and referenced downloads pass. A public HTTPS check
also passes those modes with the official
[GDAL byte.tif fixture](https://github.com/OSGeo/gdal/blob/v3.9.3/autotest/gcore/data/byte.tif);
that third-party file is not redistributed here.

Demo and user-raster output URLs remain usable after service recreation and
restart, with unchanged user-output checksums. Runtime inspection confirms the
non-root user, read-only root, dedicated result volume, dropped capabilities,
disabled privilege escalation and PROJ networking. No staged input remains
after handled executions; input cleanup and killed-worker slot recovery are
also covered by tests.

A separate 512 by 512 Float32 DEM with nodata produces a 910,778-byte input and
910,911-byte warped output. Local HTTP info and raw warp executions took about
**0.043 s** and **0.063 s**, including inline request transfer. Warped pixels
match an independent Rasterio reprojection within the comparison tolerance.
The container's cgroup memory peak rose from about **297 MiB to 304 MiB** during
this check under the release's 512 MiB limit. These are single-machine observations,
including the running workers and earlier checks, rather than worst-case bounds
or a throughput guarantee. Larger and more varied real-data workloads remain
[pilot follow-up](roadmap.md#pilot-follow-up).

The pinned Geonovum checker still matches the reviewed
[five-diagnostic baseline](../validation/geonovum/README.md). The source-input
contract improves the supported workflow without resolving scalar-reference,
job-resource or full Annex A gaps. No remote CI, new TEAM Engine run or
certification is claimed.
