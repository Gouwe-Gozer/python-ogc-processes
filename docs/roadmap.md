# Future work

Implemented behavior is described in [README](../README.md), not maintained as
a completed backlog here. These are proposals, not advertised capabilities.

- **Hosted use:** choose access control for all routes, job/result visibility,
  TLS, logging, monitoring and database/result-volume backup/maintenance before
  processing private data. See [deployment boundaries](release-image.md).
- **Client interoperability:** verify GeoTIFF file/URL controls, GeoJSON rendering,
  async polling and all output modes against a named client build. Record exact
  requests/responses; see [current limitations](validation.md#client-interoperability).
- **Raster catalogue:** choose additional operations from concrete demand.
  Cropping, resampling, band selection and hillshade are candidates. Reuse
  Rasterio/GDAL and the [existing contribution path](adding-a-process.md).
- **CRS coverage:** add target EPSG identifiers only with representative offline
  transformation tests. Resolution/extent controls require an output-pixel budget
  checked before allocation.
- **Measured capacity:** measure memory, execution time and output size before
  raising limits or adding worker scaling/object storage. Automatic retries and
  distributed execution need explicit lifecycle decisions.
- **Input reuse:** add reusable uploads only if users need them, with access,
  expiry and combined storage budgets. Current public HTTPS references and
  inline inputs already support users' own rasters.


Review conditional OGC requirements when adding input types, multiple outputs or
execution capabilities. Keep current [conformance limitations](validation.md)
public; passing a baseline is not certification. Add vector dependencies only
when a concrete operation requires them.
