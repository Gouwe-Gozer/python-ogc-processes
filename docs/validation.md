# Validation

The deterministic suite covers the real Terrio binding and fixture, independent
adapter, schemas, discovery links, input/output validation, raw/document HTTP
responses, defaults, unsupported options, sanitized failures and synchronous
preferences. Two requests traverse an actual loopback HTTP server. The release
smoke script repeats raw/document execution against Gunicorn in the container.

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
especially requirements 25–28 and 32 for synchronous mode and result shapes.
A document JSON object output uses the qualified inline `value` wrapper required
by `results.yaml`/`inlineOrRefData.yaml`. Raw returns the native output directly.
