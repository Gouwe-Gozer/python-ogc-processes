"""Point sampling: GeoJSON point geometries or a Point FeatureCollection."""

from geo_processes.contracts.files import execution_contract, json_execution_schema, metadata
from geo_processes.contracts.geojson import GEOJSON_TYPE, JSON_TYPES, VECTOR_SCHEMA

POSITION_SCHEMA = {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "number"}}
POINT_SCHEMA = {
    "type": "object",
    "required": ["type", "coordinates"],
    "additionalProperties": False,
    "properties": {"type": {"type": "string", "enum": ["Point"]}, "coordinates": POSITION_SCHEMA},
}
MULTIPOINT_SCHEMA = {
    "type": "object",
    "required": ["type", "coordinates"],
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string", "enum": ["MultiPoint"]},
        "coordinates": {"type": "array", "minItems": 1, "maxItems": 1000, "items": POSITION_SCHEMA},
    },
}
FEATURE_COLLECTION_SCHEMA = {
    "type": "object",
    "required": ["type", "features"],
    "additionalProperties": True,
    "not": {"required": ["crs"]},
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
                    "geometry": POINT_SCHEMA,
                },
            },
        },
    },
}
POINTS_SCHEMA = {"type": "object", "oneOf": [POINT_SCHEMA, MULTIPOINT_SCHEMA, FEATURE_COLLECTION_SCHEMA]}
PROCESS_METADATA = metadata(
    "raster-sample-points",
    "Sample raster at points",
    "Sample one band at 1–1,000 WGS84 longitude/latitude locations supplied as a GeoJSON Point, MultiPoint "
    "or Point FeatureCollection. Uses the containing pixel without interpolation. Returns a Point FeatureCollection; "
    "adds/replaces properties.value; nodata, nonfinite and outside samples are null. "
    "Supports value or expiring reference delivery.",
    {
        "points": {
            "title": "Sample points (GeoJSON)",
            "description": (
                "GeoJSON Point, MultiPoint or FeatureCollection of Points in WGS84 longitude/latitude, "
                "without a crs member. At most 1,000 locations in total. "
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
