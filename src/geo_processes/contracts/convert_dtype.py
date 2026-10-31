"""Explicit all-band datatype conversion contract; no implicit band selection."""

from geo_processes.contracts.files import execution_contract, json_execution_schema
from geo_processes.contracts.sources import SOURCE_DESCRIPTION, SOURCE_VALUE_SCHEMA

INPUT_SCHEMAS = {
    "dtype": {"type": "string", "enum": ["uint8", "uint16", "int16", "float32", "float64"]},
    "overflow": {"type": "string", "enum": ["error", "clip"], "default": "error"},
    "rounding": {"type": "string", "enum": ["truncate", "nearest"], "default": "truncate"},
    "nodata": {"type": "number"},
}
TIFF_SCHEMA = {"type": "string", "format": "binary"}
PROCESS_METADATA = {
    "id": "raster-convert-dtype",
    "version": "1.0.0",
    "title": "Convert raster datatype",
    "description": (
        "Convert all bands' stored pixel values, retaining grid, CRS, band count, descriptions, units, "
        "scale/offset and default-namespace descriptive tags; stale statistics are dropped. "
        "Overflow rejects by default or clips explicitly; integer conversion truncates toward zero "
        "or rounds nearest with ties to even. Nonfinite valid pixels reject. Source nodata is retained "
        "only if exactly representable; otherwise supply nodata. Masks require a nodata sentinel. "
        "Valid-pixel/nodata collisions reject. Float conversion uses IEEE rounding. "
        "Palette and GCP/RPC rasters are unsupported. Compression/layout and overviews are not preserved."
    ),
    "jobControlOptions": ["sync-execute"],
    "outputTransmission": ["value", "reference"],
    "links": [],
    "inputs": {
        "source": {
            "title": "Source GeoTIFF",
            "description": SOURCE_DESCRIPTION,
            "schema": SOURCE_VALUE_SCHEMA,
            "minOccurs": 1,
            "maxOccurs": 1,
        },
        **{
            key: {"title": key, "schema": schema, "minOccurs": int(key == "dtype"), "maxOccurs": 1}
            for key, schema in INPUT_SCHEMAS.items()
        },
    },
    "outputs": {"result": {"title": "Converted GeoTIFF", "schema": {**TIFF_SCHEMA, "contentMediaType": "image/tiff"}}},
    "example": {
        "inputs": {"source": {"href": "https://data.example.org/raster.tif", "type": "image/tiff"}, "dtype": "float64"},
        "response": "document",
    },
}


def openapi_execution():
    contract = execution_contract(
        PROCESS_METADATA,
        "image/tiff",
        TIFF_SCHEMA,
        {key: json_execution_schema(value) for key, value in INPUT_SCHEMAS.items()},
    )
    # Existing helper describes the bundled single-band operations. This
    # operation converts every band, so omit its optional band input locally.
    del contract["requestBody"]["content"]["application/json"]["schema"]["properties"]["inputs"]["properties"]["band"]
    return contract
