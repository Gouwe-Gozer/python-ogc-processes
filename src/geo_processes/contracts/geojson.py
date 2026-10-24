"""Shared GeoJSON media types and result collection envelope."""

GEOJSON_TYPE = "application/geo+json"
JSON_TYPES = (GEOJSON_TYPE, "application/json")

# Output is a FeatureCollection too; individual operations own the geometry contract.
VECTOR_SCHEMA = {
    "type": "object",
    "required": ["type", "features"],
    "properties": {
        "type": {"type": "string", "enum": ["FeatureCollection"]},
        "features": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "geometry", "properties"],
                "properties": {
                    "type": {"type": "string", "enum": ["Feature"]},
                    "geometry": {
                        "type": "object",
                        "required": ["type", "coordinates"],
                        "properties": {
                            "type": {"type": "string", "enum": ["Point", "Polygon", "MultiPolygon"]},
                            "coordinates": {"type": "array"},
                        },
                    },
                    "properties": {
                        "type": "object",
                        "required": ["value"],
                        "properties": {
                            "value": {"type": "number", "nullable": True},
                        },
                    },
                },
            },
        },
    },
}
