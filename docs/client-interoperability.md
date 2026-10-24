# Client interoperability log

Observations from testing `geo-processes` with the external OGC API – Processes
client. Client name/build and the exact `geo-processes` responses consumed by it
have not been recorded. ZOO behavior is reported by the tester, not independently reproduced.
Append issues with stable IDs; record client/service versions when available.
Schema validation and usable form rendering are separate checks.

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
- **Status:** Resolved on the service branch: the demo/`anyOf` description was
  removed and schema tests pass. The remaining plain-text rendering is CI-001.

## Planned client follow-up — original review item 2

Implement and test the user-raster workflow in a separate PR in the external
client's repository, following the service usability PR. CI-001 records the
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
