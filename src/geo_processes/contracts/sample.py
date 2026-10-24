"""Point sampling: GeoJSON Point FeatureCollection in and out."""

from geo_processes.contracts.files import execution_contract, json_execution_schema, metadata
from geo_processes.contracts.geojson import GEOJSON_TYPE, JSON_TYPES, VECTOR_SCHEMA

POINTS_SCHEMA = {
    "type": "object",
    "required": ["type", "features"],
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string", "enum": ["FeatureCollection"]},
        "features": {
            "type": "array",
            "minItems": 1,
            "maxItems": 1000,
            "items": {
                "type": "object",
                "required": ["type", "geometry", "properties"],
                "additionalProperties": False,
                "properties": {
                    "type": {"type": "string", "enum": ["Feature"]},
                    "id": {"oneOf": [{"type": "string"}, {"type": "number"}]},
                    "properties": {"type": "object", "nullable": True},
                    "geometry": {
                        "type": "object",
                        "required": ["type", "coordinates"],
                        "additionalProperties": False,
                        "properties": {
                            "type": {"type": "string", "enum": ["Point"]},
                            "coordinates": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "number"}},
                        },
                    },
                },
            },
        },
    },
}
PROCESS_METADATA = metadata(
    "raster-sample-points",
    "Sample raster at points",
    "Sample one band at 1–1,000 WGS84 longitude/latitude GeoJSON Points. Uses the containing pixel, "
    "without interpolation. Adds/replaces properties.value; nodata, nonfinite and outside samples are null. "
    "Returns GeoJSON by value or expiring reference.",
    {
        "points": {
            "title": "Sample points (GeoJSON)",
            "description": (
                "Point FeatureCollection in WGS84 longitude/latitude, without a crs member. "
                "Supply a qualified JSON value or HTTPS reference."
            ),
            "schema": {**POINTS_SCHEMA, "contentMediaType": GEOJSON_TYPE},
            "minOccurs": 1,
            "maxOccurs": 1,
        }
    },
    GEOJSON_TYPE,
    VECTOR_SCHEMA,
    {
        "points": {
            "value": {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [5.12, 52.09]}}
                ],
            },
            "mediaType": GEOJSON_TYPE,
        }
    },
)


def openapi_execution():
    return execution_contract(
        PROCESS_METADATA,
        GEOJSON_TYPE,
        VECTOR_SCHEMA,
        {"points": json_execution_schema(POINTS_SCHEMA, media_types=JSON_TYPES)},
    )
