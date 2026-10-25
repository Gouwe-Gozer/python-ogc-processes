# OGC CITE/TEAM Engine evidence

No TEAM Engine run for the current Raster Processes API service is recorded here.

This directory retains the inherited OGC API - Processes 1.0 TEAM Engine
baseline of the predecessor application. It is historical evidence, not a
conformance certificate. Known failures are retained for transparency.

The recorded execution tests used the integration-only `async-echo` process,
because the CITE suite expects its controlled input/output contract. They did
not exercise any current raster process. Current process
behavior is covered by the tests described in [validation](../../docs/validation.md).
The retained echo configuration can support a future TEAM Engine run; its
asynchronous capabilities are separate from the public synchronous API.

Keep run evidence in `baseline/`. Updating the same directory lets Git
retain older baselines without accumulating a generated result tree for every
pull request.

Retain these files from a valid TEAM Engine session:

- `testng-results.xml`: complete pass, fail and skip results;
- `earl-results.rdf`: machine-readable EARL conformance evidence;
- `teamengine-log.xml`: submitted inputs, summary and concise failures; copied
  from the session's `log.xml`;
- `README.md`: human-readable run metadata and interpretation.

The baseline README must record:

- run date in `YYYY-MM-DD` form;
- full Git commit tested;
- TEAM Engine suite and version;
- Docker image digest;
- landing-page value;
- echo-process identifier;
- whether all processes were selected;
- pass, fail and skip totals by test group;
- each known failure or skip that affects interpretation.

Do not retain the complete `html/` or `result/` directories. They duplicate the
XML evidence with generated style sheets, JavaScript and one HTML page per
test. A reviewer can inspect `testng-results.xml`, `earl-results.rdf` and the
human-readable baseline summary instead.

A changed diagnostic set must be reviewed explicitly. A newly failing test is
a regression. A resolved failure requires the baseline evidence and summary to
be updated in the same pull request so that the failure cannot silently return.
