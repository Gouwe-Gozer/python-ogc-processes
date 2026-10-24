# Client interoperability log

Observations from testing `geo-processes` with the external OGC API – Processes
client. Client name/build and the exact `geo-processes` responses consumed by it
have not been recorded. ZOO behavior is reported by the tester, not independently reproduced.
Append issues with stable IDs; record client/service versions when available.
Schema validation and usable form rendering are separate checks.

## Pending GeoJSON acceptance checks

The service now exposes `raster-sample-points` (Point FeatureCollection input
and output) and `raster-polygonize` (polygon FeatureCollection output), advertised
as `application/geo+json`. Test client file/HTTPS entry, qualified object
submission, native GeoJSON rendering and reference downloads using the
[requests and contracts](raster-operations.md). Initial input testing is recorded
in CI-003 and CI-004; successful execution, output rendering and downloads through
the external UI remain unverified. Record the client build and actual
request/response when reproducing issues.

## CI-001 — GeoTIFF rendered as plain text

- **Issue:** The tester expected file selection and HTTPS URL entry for the
  raster input. The client rendered a plain text field with neither option.
  ZOO's `OTB.MeanShiftSmoothing` image input reportedly renders correctly.
- **Category:** Interoperability; UX. No OGC compliance violation established.
- **Responsibility:** Undetermined. A difference in client detection or service
  metadata is suspected; the cause has not been isolated.
- **Evidence:** Current `source.schema` for `raster-info` and `raster-warp`, from
  [the service contract](../src/geo_processes/contracts/sources.py):

  ```json
  {
    "type": "string",
    "format": "byte",
    "contentEncoding": "binary",
    "contentMediaType": "image/tiff"
  }
  ```

  The tester-supplied ZOO description uses `schema.oneOf` with TIFF, JPEG and PNG
  string branches, each with `contentEncoding: base64` and `contentMediaType`,
  without `format: byte`. It also includes `extended-schema` alternatives for
  links and inline `value` objects, plus `raw_schema1`. Which differences the
  client uses is unknown; ZOO's example does not establish mandatory metadata.

  Both service descriptions pass the normative OGC schemas, and HTTP tests
  cover HTTPS and inline base64 ([tests](../tests/test_inputs.py),
  [schema checks](../tests/test_ogc_schemas.py)). These do not test the external UI.
  [18-062r2](https://docs.ogc.org/is/18-062r2/18-062r2.html), requirements 18 and
  22, specify input delivery; 49–51 address descriptions. The official
  [ProcessDescription.json](https://schemas.opengis.net/ogcapi/processes/part1/1.0/examples/json/ProcessDescription.json)
  uses `contentEncoding: binary` for images. None of this establishes a required
  file-picker or URL-entry widget.
- **Status:** Needs investigation. Capture the client's actual process response
  and inspect its input-detection rules; test the schema differences separately.

## CI-002 — Earlier raster description triggered JSON fallback

- **Issue:** Before the description correction, the client displayed a JSON
  textarea stating that `anyOf` was outside its supported schema subset,
  instead of the expected raster controls.
- **Category:** Interoperability; UX. The service's mixed-input description also
  required review against OGC Process Description requirement 51 (`oneOf`).
- **Responsibility:** Service for the unnecessary demo/raster combination.
  The observed client fallback alone does not establish a client compliance defect.
- **Evidence:** The tester's screenshot and the previous schema combined a
  `demo-dem` string enum with a binary raster branch using `anyOf`. The current
  contract removes that alternative; examples and tests submit the demo file
  as ordinary raster data. See [the input review](inputs.md#ogc-scope-and-deployment).
- **Status:** Resolved in the service: the demo/`anyOf` description was
  removed and schema tests pass. The remaining plain-text rendering is CI-001.

## CI-003 — MultiPoint rejected by the sampling contract

- **Issue:** The tester supplied three map locations as a GeoJSON `MultiPoint`,
  expecting raster sampling. The service returned HTTP 400 because the operation
  currently accepts only a FeatureCollection containing individual Point features.
- **Category:** Interoperability; UX. This is a supported-input restriction,
  not an established OGC compliance defect.
- **Responsibility:** Service for the narrow input contract.
- **Evidence:** Submitted GeoJSON:

  ```json
  {"type":"MultiPoint","coordinates":[[4.836065,52.647618],[4.827911,52.645173],[4.834395,52.644807]]}
  ```

  Returned detail: `points must be a GeoJSON FeatureCollection without crs or foreign members`.
  The [description](../src/geo_processes/contracts/sample.py) and
  [validator](../src/geo_processes/processes/sample.py) explicitly require that
  collection shape. A valid GeoJSON geometry need not satisfy a process-specific schema.
- **Status:** Open — usability improvement proposed: accept Point/MultiPoint
  as well as point FeatureCollections. Current workaround: submit individual
  Point features inside a FeatureCollection. No contract change has been made.

## CI-004 — Map drawing interfered with pasted JSON

- **Issue:** After pasting a FeatureCollection example, the client reported
  invalid JSON. The tester subsequently identified that previously drawn map
  points were being inserted back into the edited field. Expected: pasting a
  replacement value leaves one valid JSON document; actual: map/editor updates
  interfered with the pasted content.
- **Category:** UX; interoperability. No OGC compliance violation established.
- **Responsibility:** Client for map/editor synchronization; the precise update
  mechanism has not been independently reproduced.
- **Evidence:** Reported client message:
  `JSON.parse: expected ',' or ']' after array element at line 1 column 88 of the JSON data`.
  The tester attributed it to map-drawn points appearing in the pasted JSON
  field. Exact field contents, client build and event sequence were not captured;
  this message supplies no evidence of a new service response.
- **Status:** Open — reproduce by drawing points, pasting a replacement
  FeatureCollection and checking the field before execution. Verify that map
  updates replace or reconcile the editor value without concatenating content
  or overwriting a newer manual edit. Clearing drawn points before pasting is
  a possible workaround, not yet verified.

## Planned client workflow follow-up

Implement and test the user-raster workflow in the external client's repository.
The service contract is available; CI-001 records the
observed input-rendering problem; output handling still needs verification.

- Recognize the advertised binary GeoTIFF value schema and provide local-file
  selection and HTTPS URL entry. Submit local files as qualified inline base64
  and URLs as `href` references, following the [input contract](inputs.md).
- Present raster information and handle GeoTIFF results through the supported
  [response modes](results.md#http-contract): native bytes, inline base64,
  document references and raw references delivered through HTTP 204 plus `Link`.
  Let users download and save file results.
- Show useful [API error details](errors.md), including unavailable/expired
  results, and add client regression tests using captured service descriptions,
  requests and responses. Record both client and service versions.
- **Category:** Interoperability; UX. Widget choices alone are not evidence of
  an OGC compliance violation.
- **Responsibility:** Client for this planned implementation and verification.
  CI-001's underlying cause remains undetermined until reproduced and isolated.
- **Evidence:** The linked input/result contracts, [local-file example](../scripts/process_raster.py)
  and [service HTTP tests](../tests/test_warp.py) provide reference exchanges;
  they do not establish the external client's current output behavior.
- **Status:** Open — planned client work. Reproduce CI-001 and verify the output
  modes before classifying further behavior as a confirmed defect.
