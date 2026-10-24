# Roadmap: geo-processes and users' own rasters

The goal is an API where **users submit their own rasters**, select a process
and receive usable results. A service limited to an operator's hosted dataset
catalogue is not the intended end state. Supporting user-supplied data belongs
in the first useful-service milestone, before building a large process catalogue.

This document distinguishes implemented foundations from future milestones.
The API accepts user GeoTIFFs through HTTPS references or inline base64;
see [inputs](inputs.md), [README](../README.md) and
[validation](validation.md) for the contract and evidence boundary.

## Completed foundation: Rasterio pivot

The [Rasterio pivot](rasterio-pivot.md) renames the project to `geo-processes`
and implements Rasterio-backed `raster-info` and `raster-warp`, preserving the
tested service infrastructure.

## Implemented user-raster milestone

The user selected HTTPS references and qualified inline base64 for the first
flow. Both current processes use the same input resolver, validate staged data
and remove inputs after execution independently of result expiry. Tests cover
actual local TLS, destination/redirect policy, both source forms and all four
warp output modes. A separate client can create its own raster and run the
complete flow; see [input examples and policy](inputs.md).

## Pilot follow-up

- Expand representative DEM and imagery cases across users' data types, band
  counts, nodata and CRSs before broadening formats or increasing limits.
- Measure memory, runtime and output size against the existing 16 MiB and
  1,048,576-sample bounds; deployment/result limits are in [results](results.md).
- Decide whether repeated processing needs reusable uploads or input storage.
  That would be a documented extension with access, privacy and expiry policies.
- Establish the intended users and hosting/access policies before opening a
  shared public service. Keep the current synchronous pilot bounded.

Keep the tiny bundled TIFF for deterministic regression tests. Small, suitably
licensed representative fixtures should keep CI independent of public data
servers. An operator-configured catalogue and dataset discovery can remain an
optional convenience, not a prerequisite or substitute for user submission.

## Useful warp controls and the next operation

Warp currently retains the source width and height. Add deliberate target
resolution or extent controls when real-data use cases establish the needed
contract, with an output-pixel budget checked before allocation. Merely raising
file-size limits is insufficient for compressed inputs or enlarged outputs.

Choose the next process after the user-input milestone from concrete user
needs. Cropping, resampling, band selection and hillshade are candidates.
Confirm the required algorithm is available or define its implementation;
do not assume that Rasterio exposes every GDAL processing algorithm directly.
Each process should reuse input resolution and the tested result lifecycle
while owning its parameters, description, validation and output contract.

## Growing the raster and vector process catalogue

Use [Rasterio](https://rasterio.readthedocs.io/en/stable/) for raster work.
Later operations may use [Shapely](https://shapely.readthedocs.io/en/stable/)
for geometry, [Pyogrio](https://pyogrio.readthedocs.io/en/stable/) for vector
file I/O and [GeoPandas](https://geopandas.org/en/stable/) for spatial tables.
Introduce direct dependency declarations when those libraries are used;
availability through another dependency is not an application contract.
Validate supported algorithms and formats against the pinned environments.

| Candidate | Main additional work |
| --- | --- |
| Hillshade, cropping, resampling, band selection | Explicit parameters, validation and pixel-level result checks |
| Geometry operations and vector file I/O | Per-operation schemas, CRS/units, supported formats and feature limits |
| Mosaics and raster calculations | Multiple inputs, CRS/grid alignment and combined input/output budgets |

Keep one public process implementation and description per operation. A small
shared helper can remove repeated raster-response formatting when the next
process makes that duplication concrete. Preserve explicit output identifiers,
formats and transmission modes; avoid a generic passthrough of library options
or an engine plugin framework. The [architecture](architecture.md) identifies
the boundaries, and the [OGC review guide](validation.md#ogc-review-guide) gives
the contract review points for each addition.

The project accepts Rasterio's GDAL dependency. The
[pivot decision](rasterio-pivot.md) records the removal of the active Terrio
integration and the retained historical records.

## From a useful pilot to a hosted service

A first pilot needs real user input, useful processing and independently
retrievable results, with measured and documented operating limits. Choose
access control and input/result visibility for the intended users, including
any upload storage; the present opaque result URLs are accessible to anyone
who has them. Record hosting, TLS, logging and storage maintenance decisions
alongside the [release deployment](release-image.md).

Keep execution synchronous while measured workloads fit comfortably inside the
configured request timeout. Queuing, asynchronous jobs, object storage and
distributed workers should follow demonstrated workload needs as separate
milestones. The current store permits one writer at a time and returns 503
when busy or full; this must be accounted for when assessing pilot capacity.

OGC conformance is a parallel workstream, not something implied by a usable
pilot or a larger process catalogue. Review the outstanding scalar-input-reference
and Core job-resource gaps, map evidence to Annex A and run appropriate current
service checks before strengthening conformance claims. Async execution remains
a separate workload decision; a static checker baseline is not certification.
