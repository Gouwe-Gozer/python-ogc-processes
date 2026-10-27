# Changelog

## 0.1.0 — Unreleased

- Generate TEAM Engine's official HTML report and shareable ZIP during CLI CITE
  validation, retaining native XML/EARL and linking from the local summaries.

- Scope Callback conformance to each manager's subscriber capability instead of
  mutating pygeoapi's global declarations during manager construction.
- Move shared input/execution exceptions into `errors.py`, preserving their
  HTTP/OGC contracts and keeping processors independent of the manager module.

- Preserve pygeoapi's native route prefix in result references and distinguish
  upstream HTTP status failures from unsupported content encoding.
- Cover JSON Accept headers, sync preferences, public-reference chaining and
  private-DNS rejection; document proxy/worker requirements and inherited job routes.

- Correct inherited Features CRUD/CQL2 claims for read-only sample providers;
  omit unsupported CQL query POSTs from OpenAPI and reject ignored filters.
- Make the README's first raster-processing example runnable with the packaged
  AHN4 sample, including the GeoTIFF download, and clarify synchronous execution.
- Keep Bandit suppression explanations outside its directive syntax, removing
  false unknown-test-name warnings without changing security checks.

- Add shared Make validation commands, locked Geonovum 1.3.2 tooling and a
  manual CITE workflow against the real synchronous application. Preserve
  native reports and propose a fresh, explicitly classified current-service baseline.

- Consolidate historical documentation and remove completed rename instructions;
  document required manager placeholders, forward the documented terms URL
  in Compose and exclude local artifacts from the Docker build context.

- Adopt Raster Processes API / `raster-processes` branding and subtitle in service
  metadata, documentation and Docker images; update exception-document links and
  document the GitHub/local rename steps. Python imports and process IDs remain unchanged.

- Remove unused OpenAPI tag declarations while preserving endpoints/groupings,
  explain intended OGC alignment, and record PostgreSQL async readiness findings.

- Publish the supplied points and a nearby raster-contained polygon through
  native read-only OGC Features collections, alongside the unchanged AHN4 TIFF.
- Accept collection-level Features metadata in sampling inputs and validate
  sample discovery, paging, media types and raster alignment.

- Preserve pygeoapi's JSON-LD landing catalogue instead of treating it as an
  ordinary JSON links document; guard unexpected JSON body shapes.

- Restore the ReDoc documentation page with a pinned compatible bundle through
  pygeoapi's template override, and cover HTML processor-name locale warnings.

- Filter pygeoapi's false metadata locale warnings and remove the unused
  AsyncAPI file setting from the image, retaining normal logging and translation.

- Accept GeoJSON Point and MultiPoint sampling inputs alongside point
  FeatureCollections, preserving the same WGS84 contract and point-count limit.

- Add synchronous point sampling, range reclassification and categorical
  polygonization, with explicit band/CRS/complexity limits and GeoJSON contracts.
- Reuse TIFF delivery for reclassification and extend shared expiry/quota/download
  handling to GeoJSON, without new dependencies or asynchronous infrastructure.

- Audit Core Requirements 1–46; fix scalar references, job exception URIs and
  descriptions, required landing links and traversable process pagination.
- Reuse shared reference/error handling with async managers and record the
  conditional checker findings instead of advertising unsupported responses.
- Expose synchronous `raster-info` and `raster-warp` through pygeoapi 0.24.0,
  with Rasterio 1.4.3, NumPy 1.26.4 and application-owned metadata contracts.
- Accept users' GeoTIFFs through controlled HTTPS references or inline base64;
  bound request/raster sizes, validate staged data and clean inputs after use.
- Describe binary raster values using OGC conventions, independently of transport.
- Deliver warp results as native TIFF, qualified base64 or download references,
  with bounded storage, expiry, atomic publication and cross-worker locking.
- Provide a local-file inspection/reprojection/download command, a JSON exception
  URI catalogue and startup validation with effective configuration feedback.
- Retain hardened release deployment, independent-client smoke checks, quality
  tooling and reviewed Geonovum diagnostics using Node 24.
- Document operation contributions, current OGC limitations and client follow-up.
- Consolidate maintained documentation and archive superseded planning material.

## Project history

The service derives MIT-licensed infrastructure from `bkn-terrain-processes`.
Initial demo-only backend milestones were replaced by the Rasterio implementation
and user-raster inputs. See [project history](docs/history.md); previous detailed changelogs
remain in Git history. Predecessor validation and release numbers do not describe
this service.
