# Validation

The deterministic suite covers the real Terrio binding and fixture, independent
adapter, schemas, discovery links, input/output validation, raw/document HTTP
responses, defaults, unsupported options, sanitized failures and synchronous
preferences. Loopback HTTP tests also retrieve and inspect generated GeoTIFFs.
The warp tests cover all supported CRSs, both resampling methods, all four
response/transmission combinations, defaults, storage bounds, expiry, safe
paths and concurrent writers. The release smoke scripts repeat execution and
download checks against Gunicorn. CI uses a separate client container and tests
that issued result URLs survive a server restart.

Official OGC API – Processes 1.0 schemas are stored under `tests/schemas` for
offline validation. They are schemas, not the example JSON documents linked in
the handover. The output schema additionally describes the pinned Terrio result.

The public service advertises the Processes 1.0 Core, JSON, OpenAPI 3.0 and OGC
Process Description classes, plus upstream Common and HTML discovery classes.
It does not advertise Callback, Job List or Dismiss. This is a bounded contract
implementation, not a claim of complete conformance or OGC certification.
Full input-reference interoperability, multipart outputs and all of Annex A
have not been implemented or validated.

The pinned Geonovum 1.2.0 checker statically inspects OpenAPI. Its known job/async
diagnostics are recorded separately; they do not justify inventing unimplemented
capabilities. See [its baseline](../validation/geonovum/README.md).
The inherited CITE/TEAM Engine echo fixture and historical reports remain for
future validation work. Those reports tested the predecessor service and are
**not Terrio validation evidence**; no new TEAM Engine run is claimed.

The normative basis is [OGC Processes 1.0, sections 7.10–7.11 and Annex A](https://docs.ogc.org/is/18-062r2/18-062r2.html),
especially requirements 25–28, 30 and 32 for synchronous mode and result shapes.
A document JSON object output uses the qualified inline `value` wrapper required
by `results.yaml`/`inlineOrRefData.yaml`. Raw returns the native output directly.

## Published binary-schema limitation

The unchanged official `inputValueNoObject.yaml` contains a `oneOf` with both
an unrestricted string and a byte-formatted string. A valid base64 string
matches both branches, so strict official-schema validation rejects inline
binary values even when a base64 format checker is supplied. A focused test
records the overlap. The normative binary example uses base64 with `encoding`
and `mediaType`, which is what document/value warp responses return.

Process discovery, execution requests, exceptions and reference documents are
validated against the official offline schemas. Inline binary documents are
validated against the explicit application schema and decoded into real
GeoTIFFs. No upstream schema fixture was modified to hide this discrepancy,
and no claim of complete official-schema or OGC conformance is made.
