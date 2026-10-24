# JSON exception catalogue

JSON errors from process discovery, execution and result downloads use `type`,
`title`, `status` and `detail`. The existing `code` and `description` remain for
clients already using them; `description` equals `detail`. Clients should branch on `type` or
`code`, rather than matching human-readable messages.

The [official exception schema](https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi/schemas/exception.yaml)
permits these fields and additional properties. [OGC Part 1, Requirement 15](https://docs.ogc.org/is/18-062r2/18-062r2.html)
specifies the unknown-process URI below. The other URIs are **service-defined**
policy and failure types, rather than additional OGC exception definitions.
This catalogue covers JSON responses; upstream HTML error pages are unchanged.

| Legacy `code` | HTTP | `type` |
| --- | --- | --- |
| `NoSuchProcess` | 404 | `http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/no-such-process` |
| `InvalidParameterValue` | 400 | [Invalid parameter value](#invalid-parameter-value) |
| `RequestTooLarge` | 413 | [Request too large](#request-too-large) |
| `ServerBusy` | 503 | [Server busy](#server-busy) |
| `NoSuchResult` | 404 | [No such result](#no-such-result) |
| `NoApplicableCode` | 500 | [Processing failed](#processing-failed) |

Each service-defined URI is the full URL of its section in this document, under
`https://github.com/Gouwe-Gozer/terrio-processes/blob/main/docs/errors.md`.
The repository still has its original name. Treat published type URIs as stable
identifiers if the repository is renamed later.

For example, a malformed execution request returns HTTP 400, `application/json`:

```json
{
  "type": "https://github.com/Gouwe-Gozer/terrio-processes/blob/main/docs/errors.md#invalid-parameter-value",
  "title": "Invalid request",
  "status": 400,
  "detail": "inputs must be an object",
  "code": "InvalidParameterValue",
  "description": "inputs must be an object"
}
```

## Invalid parameter value

A malformed request, missing/unknown input or output, unsupported option, failed
HTTPS input validation, or invalid raster. Fix the request before retrying.
Sample/block limits are validation errors (400), distinct from byte limits.

## Request too large

The execution document exceeds 24 MiB or the supplied raster exceeds 16 MiB.
Reduce the input; retries with the same data will not help. See [input limits](inputs.md).

## Server busy

Input staging slots, the result writer or result capacity are unavailable.
Retry later; a full result store may require expiry or operator maintenance.
No automatic retry loop or guaranteed retry time is advertised.

## No such result

A download identifier is invalid, missing or expired. These application result
URLs are separate from OGC job resources: this is not `no-such-job`.

## Processing failed

An unexpected processing or storage failure. Public details are sanitized;
operators use server logs to investigate. Internal paths and tracebacks are not
returned to clients. Configuration failures should instead stop startup; see
[startup validation](development.md#startup-validation).

The OpenAPI document includes the official exception schema and representative
catalogue examples. HTTP tests validate actual error documents against the
unchanged official schema. This does not resolve the separate Core job-resource
and other conformance gaps recorded in [validation](validation.md).
