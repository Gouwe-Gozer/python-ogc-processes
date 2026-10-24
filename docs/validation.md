# Validation

The deterministic suite covers the real Rasterio binding and fixture, independent
adapter, schemas, discovery links, input/output validation, raw/document HTTP
responses, defaults, unsupported options, sanitized failures and synchronous
preferences. Loopback HTTP tests also retrieve and inspect generated GeoTIFFs.
User-input tests submit independent multiband GeoTIFFs through inline base64 and
a real local HTTPS fixture. They exercise TLS verification, pinned connections,
destination/redirect policy, streaming bounds, deadlines and temporary cleanup.
The warp tests cover all supported CRSs, both resampling methods, all four
response/transmission combinations, defaults, storage bounds, expiry, safe
paths and concurrent writers. The release smoke scripts repeat execution and
download checks against Gunicorn. CI uses a separate client container and tests
that issued result URLs survive a server restart.

Official OGC API – Processes 1.0 schemas are stored under `tests/schemas` for
offline validation. They are schemas, not the example JSON documents linked in
the handover. The output schema additionally describes the pinned Rasterio result.

The public service advertises the Processes 1.0 Core, JSON, OpenAPI 3.0 and OGC
Process Description classes, plus upstream Common and HTML discovery classes.
It does not advertise Callback, Job List or Dismiss. This is a bounded contract
implementation, not a claim of complete conformance or OGC certification.
Full input-reference interoperability, multipart outputs and all of Annex A
have not been implemented or validated.

In particular, input references are a Core requirement (18). Raster-source
references are supported, but scalar CRS/resampling references remain unsupported.
Core also defines job status/results resources (35 and 38), which remain
conformance gaps even though the current processes advertise only synchronous
execution. A passing diagnostic baseline does not resolve them.
[OGC Processes 1.0](https://docs.ogc.org/is/18-062r2/18-062r2.html)

The pinned Geonovum 1.2.0 checker statically inspects OpenAPI. Its known job/async
diagnostics are recorded separately; they do not justify inventing unimplemented
capabilities. See [its baseline](../validation/geonovum/README.md).
The inherited CITE/TEAM Engine echo fixture and historical reports remain for
future validation work. Those reports tested the predecessor service and are
**not Rasterio validation evidence**; no new TEAM Engine run is claimed.

The normative basis is [OGC Processes 1.0, sections 7.10–7.11 and Annex A](https://docs.ogc.org/is/18-062r2/18-062r2.html),
especially requirements 25–28, 30 and 32 for synchronous mode and result shapes.
A document JSON object output uses the qualified inline `value` wrapper required
by `results.yaml`/`inlineOrRefData.yaml`. Raw returns the native output directly.

## OGC review guide

Use [OGC API – Processes Part 1: Core 1.0.0][processes-core] as the normative
reference. These pointers guide review; they are not a completed conformance
matrix. The [roadmap](roadmap.md) records the user-raster goal and future scope.

| Review area | Standard pointer | Current evidence or remaining work |
| --- | --- | --- |
| Discovery and claims | Sections 7.4, 7.9–7.10 | [HTTP tests](../tests/test_http_contract.py), [official-schema tests](../tests/test_ogc_schemas.py); claims still need a full audit |
| Per-operation descriptions | Section 8 | [Contracts](../src/geo_processes/contracts/) and [OpenAPI tests](../tests/test_openapi_patch.py) |
| Input references and validation | Section 7.11.2, requirements 18, 22 and 24 | [HTTPS/base64 policy](inputs.md), [input tests](../tests/test_inputs.py); scalar references remain unsupported |
| Execution preferences/defaults | Section 7.11.2, requirements 25–27 | [Info HTTP tests](../tests/test_http_contract.py) and [warp tests](../tests/test_warp.py) |
| Synchronous results | Section 7.11.4, requirements 28, 30 and 32 | Four single-output warp combinations; [result lifecycle](results.md) |
| Multiple raw outputs | Section 7.11.4, requirements 29 and 31 | Multipart representations not implemented |
| Job resources | Sections 7.12–7.13 | Not implemented; see the [checker baseline](../validation/geonovum/README.md) |
| OpenAPI and exceptions | Section 10 | [Generator](../src/geo_processes/openapi.py), schema/HTTP tests and [development checks](development.md) |
| Conformance assessment | [Annex A][abstract-tests] | Partial local evidence; no current-service certification claim |

For each new operation or input route:

1. Review the relevant clauses above before choosing its request and response
   contract. Record unsupported cases and any remaining standards gaps.
2. Keep the process description, validation, generated OpenAPI and executable
   examples consistent. Include units, nodata behavior, cardinality, resource
   limits and supported formats. Retain the actual raw/document defaults.
3. Validate HTTP documents against the [official schemas][official-schemas]
   using the unchanged [offline snapshot](../tests/schemas/ogc-processes-1.0/README.md).
   The [official examples][official-examples] illustrate requests and responses;
   they are not schemas. Preserve the binary-schema limitation below.
4. Test the resulting pixels and metadata through the actual raster library,
   plus actual HTTP status, media type, headers and exception documents. For
   references, test resolution, policy failures, downloads and expiry from an
   independent client. Reuse [warp smoke coverage](../scripts/smoke_warp.py)
   and the [independent user-raster client](../scripts/smoke_inputs.py).
5. Run the [existing checks](development.md), regenerate OpenAPI and review
   `/conformance` alongside the runtime behavior. Deliberately review checker
   changes; do not update baselines just to obtain a passing build. Map evidence
   and gaps to Annex A before strengthening conformance claims.

The custom `/results/<id>/output.tif` download is an output reference target;
it is not an implementation of `/jobs/{jobID}/results`. A future input upload
endpoint would likewise be a documented extension, not proof of Core conformance.

The [Rasterio pivot](rasterio-pivot.md) records checks for the new backend and
process names. Historical Terrio results remain separate evidence.

[processes-core]: https://docs.ogc.org/is/18-062r2/18-062r2.html
[abstract-tests]: https://docs.ogc.org/is/18-062r2/18-062r2.html#_abstract_test_suite
[official-schemas]: https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi/schemas/
[official-examples]: https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/

## Published binary-schema limitation

The unchanged official `inputValueNoObject.yaml` contains a `oneOf` with both
an unrestricted string and a byte-formatted string. A valid base64 string
matches both branches, so strict official-schema validation rejects inline
binary values even when a base64 format checker is supplied. A focused test
records the overlap for both execution inputs and result documents. The normative
binary example uses base64 with `encoding` and `mediaType`, which is what inline
raster inputs accept and document/value warp responses return.

Process discovery, dataset-ID/reference execution requests, exceptions and
reference result documents are validated against the official offline schemas.
Inline binary requests and responses are validated against the explicit
application schemas and decoded into real GeoTIFFs. No upstream schema fixture
was modified to hide this discrepancy,
and no claim of complete official-schema or OGC conformance is made.
