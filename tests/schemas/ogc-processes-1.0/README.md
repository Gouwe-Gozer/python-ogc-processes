# Official OGC Processes 1.0 schemas

The initial snapshot was downloaded unchanged on 2026-10-23 from:
https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi/schemas/

The roots are process.yaml, processList.yaml, execute.yaml, results.yaml,
exception.yaml, confClasses.yaml and landingPage.yaml (added unchanged on
2026-10-24); all their relative references are included.
SHA256SUMS.json records this snapshot. Tests resolve references entirely offline.

These are the official OpenAPI 3.0 schemas (JSON Schema Draft 4 vocabulary),
not the example JSON documents. OGC owns the upstream material; see the
copyright and licence in https://docs.ogc.org/is/18-062r2/18-062r2.html.

`statusInfo.yaml` and `statusCode.yaml` were added unchanged on 2026-10-30 for
durable async status/acceptance regression tests.

`jobList.yaml` was added unchanged on 2026-10-31 for Job List HTTP/schema tests;
its status/link dependencies were already included.
