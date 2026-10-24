"""Explicit half-open numeric ranges mapped to integer classes."""

from geo_processes.contracts.files import execution_contract, json_execution_schema, metadata

CLASSES_SCHEMA = {
    "type": "array",
    "minItems": 1,
    "maxItems": 128,
    "items": {
        "type": "object",
        "required": ["min", "max", "value"],
        "additionalProperties": False,
        "properties": {
            "min": {"type": "number"},
            "max": {"type": "number"},
            "value": {"type": "integer", "minimum": -2147483647, "maximum": 2147483647},
        },
    },
}
TIFF_SCHEMA = {"type": "string", "format": "binary"}
PROCESS_METADATA = metadata(
    "raster-reclassify",
    "Reclassify raster",
    "Map one band through 1–128 non-overlapping [min, max) intervals to int32 classes. "
    "Unmatched, masked and nonfinite pixels become nodata (-2147483648). "
    "Retains source grid and CRS; returns a one-band GeoTIFF by value or expiring reference.",
    {
        "classes": {
            "title": "Classification ranges",
            "description": (
                "Array of {min, max, value}; lower bound inclusive, upper bound exclusive. "
                "Adjacent ranges are allowed; overlaps are rejected."
            ),
            "schema": CLASSES_SCHEMA,
            "minOccurs": 1,
            "maxOccurs": 1,
        }
    },
    "image/tiff",
    TIFF_SCHEMA,
    {"classes": [{"min": 0, "max": 10, "value": 1}, {"min": 10, "max": 100, "value": 2}]},
)


def openapi_execution():
    return execution_contract(
        PROCESS_METADATA, "image/tiff", TIFF_SCHEMA, {"classes": json_execution_schema(CLASSES_SCHEMA)}
    )
