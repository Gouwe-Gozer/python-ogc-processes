# Core audit — 2026-10-24

Audit of [OGC API – Processes Part 1: Core 1.0.0](https://docs.ogc.org/is/18-062r2/18-062r2.html),
Requirements 1–46, starting from `main` at `d762836`, extended for sampling,
reclassification and polygonization. The public profile now has five processes,
synchronous execution, inputs with `maxOccurs: 1`, one output per process and
no retained jobs. Optional conditions below are
assessed against that profile, not implemented as artificial test processes.

The confirmed implementation gaps were corrected and covered by regressions.
This is a code/runtime audit, not an OGC certificate or a new TEAM Engine run.
The published binary-schema overlap remains an external validation limitation.

## Findings and corrections

- Scalar inputs now accept controlled HTTPS JSON/text references and qualified
  inline values. The shared resolver fetches, decodes and validates the resulting
  string against the same enum used for literal values. See [input policy](inputs.md).
- Both job routes return the prescribed `no-such-job` URI for unknown IDs,
  including HTML. The API exception renderer also handles `result-not-ready`
  with the existing TinyDB diagnostic manager.
- OpenAPI describes the existing job routes honestly: the current public manager
  returns 404 for every ID. It does not invent reachable success responses.
- Landing responses expose the full OGC conformance relation. Limited process
  lists preserve paging parameters in self/alternate links and supply working
  next/previous links in JSON, HTML and Link headers.

## Requirement matrix

Evidence abbreviations refer to the test files linked below. Conditional rows
must be reassessed when adding new input/output types or execution capabilities.

| Requirement | Applicability and evidence |
| --- | --- |
| 1–2: landing page | Core tests: HTTP 200, unchanged official ordinary-JSON landing schema, required JSON/HTML relations and HTTP links; JSON-LD preserves the upstream DataCatalog body for query/Accept negotiation |
| 3–4: API definition | Core tests follow definition/documentation links; OpenAPI is structurally valid |
| 5–6: conformance | Official-schema and HTTP tests verify the endpoint, schema and current classes |
| 7: HTTP | Unsupported execution methods return 405/Allow; release HTTP/1.1 verified against Gunicorn. Service TLS is a deployment responsibility if enabled |
| 8–12: process list/limit/links | Core tests traverse limited pages and alternatives, check self-link fidelity, invalid parameters, and default/max limits with a 60-process test registry |
| 13–14: description | Official-schema and HTTP tests retrieve all five independent descriptions |
| 15: unknown process | Exception/Core tests verify 404 and `no-such-process` in JSON and HTML |
| 16–17: execution operation/document | HTTP/input tests exercise actual POST routes, valid wire schemas and controlled malformed requests; binary snapshot caveat below |
| 18: inline/reference inputs | Real local TLS tests exercise raster, scalar and structured JSON references, literals, base64 and qualified values, including ordinary link metadata |
| 19: repeated inputs | Not triggered: all inputs have `maxOccurs: 1`; `classes` is one array-valued input, not repeated occurrences |
| 20: object-valued inputs | Sampling accepts qualified GeoJSON Point, MultiPoint and Point FeatureCollection objects and rejects bare object values; actual execute/results documents validate against the official schemas |
| 21: mixed-media inputs | Not triggered: each input has one value format; GeoJSON/JSON and TIFF media-type aliases do not introduce distinct value schemas |
| 22: inline binary | Input/schema tests decode direct and qualified base64 into actual GeoTIFFs |
| 23: bounding boxes | No bbox-valued input is offered; no extra operation is added to make this condition exercisable |
| 24: input validation | Inputs are validated before processing; resolved scalar strings use the same choices as inline values. Tests cover invalid JSON, wrong types/values, transport limits and cleanup |
| 25–26: execution mode | HTTP/warp tests verify synchronous defaults and synchronous handling of `Prefer: respond-async`, without an applied async preference or job Location |
| 27: default outputs | Info/warp tests verify omission selects the defined output |
| 28: raw/value, one output | Actual JSON info, TIFF and GeoJSON response tests verify media types, status and contents |
| 29: raw/value, multiple outputs | Not triggered: each public process has one output |
| 30: raw/reference | All four file-producing operations verify empty 204 and downloadable Link targets |
| 31: mixed multi-output delivery | Not triggered: each public process has one output |
| 32: document results | All processes verify output-keyed documents, qualified values and references; GeoJSON remains a qualified object, TIFF base64 retains the binary snapshot caveat below |
| 33: synchronous job creation | Not triggered under Permission 7: no retained job is created or advertised |
| 34: asynchronous execution success | Not triggered: no public process negotiates asynchronous execution |
| 35–38: job operations/status/errors | Existing routes accept GET; Core tests verify required unknown-job 404/type in JSON/HTML. No public known-job success exists because no jobs are retained |
| 39–43: retained job results | Not triggered: no public retained jobs; direct execution/result downloads are tested separately |
| 44: unknown job results | Core tests verify 404 and `no-such-job` |
| 45: results not ready | No public running jobs. An actual TinyDB-manager regression verifies the shared renderer uses `result-not-ready` for its running-job fixture |
| 46: failed job results | No public retained failed jobs. Synchronous processing failures retain appropriate HTTP status and sanitized details |

Test files: [Core](../tests/test_core_conformance.py),
[HTTP](../tests/test_http_contract.py), [inputs](../tests/test_inputs.py),
[warp](../tests/test_warp.py), [exceptions](../tests/test_errors.py),
[new raster operations](../tests/test_raster_operations.py),
[official schemas](../tests/test_ogc_schemas.py), [OpenAPI](../tests/test_openapi_patch.py).
The landing-page schema was added unchanged to the offline snapshot with its
checksum; existing official schema files were not altered.

## Checker interpretation

The [reviewed Geonovum baseline](../validation/geonovum/README.md) has eight
findings. The original audit replaced two missing-job-path findings with
expectations for job status/results HTTP 200. Those responses are unreachable
without a retained job. Five async-201 findings (one per synchronous process)
and one optional Job List finding remain. Expanding the catalogue added only
the three corresponding async expectations; all earlier findings were unchanged.
OpenAPI therefore documents actual current responses instead of declaring
unsupported 200/201 behavior solely to silence this checker.

The standard's Permission 7 makes synchronous job creation optional. The raw
checker report and applicability analysis serve different purposes; a baseline
comparison alone establishes neither a defect nor conformance.

## Async migration boundary

The changes here are useful in both modes: controlled reference resolution,
value validation, discovery/pagination and exception rendering. A regression
using the existing TinyDB manager verifies job exceptions. Another generates
its OpenAPI and verifies existing job-success responses remain intact.

Switching public processing to TinyDB is not a configuration-only replacement:
the pinned base execution handler wraps document results in an `outputs` array,
does not invoke our processor `format_result()`, and does not understand the
warp result/response objects. Its background work runs in-process threads and
its output files have no expiry cleanup. Async work therefore needs deliberate
representation integration, job/result retention and interrupted-worker policy.
If synchronous jobs are retained then, Requirement 33 also needs monitor links.

No substitute job store, worker queue, fake jobs or advertised async execution
was introduced for this audit. Revisit job-success and multi-value/output rows
when those capabilities are actually implemented.

## Verification boundary

401 tests pass with 95.40% application coverage. Ruff, Bandit and release smoke/
isolation checks pass. The release was checked for HTTP/1.1, CORS, discovery,
pagination, job errors and qualified-scalar warp execution. Local TLS tests cover
actual referenced scalar/raster transport without public-network test dependencies.

Strict validation of inline binary execute/results documents still encounters
the unchanged official `oneOf` overlap. The API follows the specified base64
representation and uses application schemas plus actual raster decoding;
see [the recorded limitation](validation.md#published-binary-schema-limitation).
A full external Annex A/TEAM Engine assessment and deployment-specific HTTPS
verification are separate evidence, not implied by these results.
