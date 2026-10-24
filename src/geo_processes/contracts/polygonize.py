"""Categorical polygonization with explicit complexity limits."""

from geo_processes.contracts.files import execution_contract, json_execution_schema, metadata
from geo_processes.contracts.geojson import GEOJSON_TYPE, VECTOR_SCHEMA

CONNECTIVITY_SCHEMA = {"type": "integer", "enum": [4, 8], "default": 4}
PROCESS_METADATA = metadata(
    "raster-polygonize",
    "Polygonize raster classes",
    "Convert contiguous equal values of one int8/uint8/int16/uint16/int32 band into WGS84 GeoJSON polygons. "
    "Nodata/masked pixels are excluded. At most 65,536 source pixels, 4,096 features and 16 MiB GeoJSON. "
    "Use reclassify first for continuous rasters. Returns GeoJSON by value or expiring reference.",
    {
        "connectivity": {
            "title": "Pixel connectivity",
            "description": "4 joins edge-sharing pixels; 8 also joins corner-sharing pixels.",
            "schema": CONNECTIVITY_SCHEMA,
            "minOccurs": 0,
            "maxOccurs": 1,
        }
    },
    GEOJSON_TYPE,
    VECTOR_SCHEMA,
    {},
)


def openapi_execution():
    return execution_contract(
        PROCESS_METADATA, GEOJSON_TYPE, VECTOR_SCHEMA, {"connectivity": json_execution_schema(CONNECTIVITY_SCHEMA)}
    )
