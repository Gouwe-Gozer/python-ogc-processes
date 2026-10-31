"""Operation-specific Shapely contract, following the independent text example."""

from copy import deepcopy

from geo_processes.contracts.files import json_execution_schema

GEOMETRY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "oneOf": [
        {
            "required": ["type", "coordinates"],
            "properties": {
                "type": {"enum": ["Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"]}
            },
        },
        {"required": ["type", "geometries"], "properties": {"type": {"enum": ["GeometryCollection"]}}},
    ],
    "properties": {
        "type": {"type": "string"},
        "coordinates": {"type": "array"},
        "geometries": {"type": "array", "items": {"type": "object"}},
    },
}
PROCESS_METADATA = {
    "id": "geometry-intersection",
    "version": "1.0.0",
    "title": "Geometry intersection",
    "description": (
        "Planar intersection of valid 2D CRS84 GeoJSON geometries, at most 10000 positions each, "
        "8 nested collection levels and 256 KiB per input. Use qualified GeoJSON/JSON values or "
        "controlled HTTPS references. No geodesic/antimeridian correction. Empty results use an "
        "empty GeometryCollection. Invalid topology and foreign geometry members are rejected."
    ),
    "jobControlOptions": ["sync-execute"],
    "outputTransmission": ["value"],
    "links": [],
    "inputs": {
        key: {"title": key, "schema": GEOMETRY_SCHEMA, "minOccurs": 1, "maxOccurs": 1} for key in ("left", "right")
    },
    "outputs": {
        "intersection": {
            "title": "Intersection",
            "schema": {**GEOMETRY_SCHEMA, "contentMediaType": "application/geo+json"},
        }
    },
    "example": {
        "inputs": {
            key: {"value": {"type": "Point", "coordinates": [4.75, 52.63]}, "mediaType": "application/geo+json"}
            for key in ("left", "right")
        },
        "response": "document",
    },
}
EXECUTE_SCHEMA = {
    "type": "object",
    "required": ["inputs"],
    "additionalProperties": False,
    "properties": {
        "inputs": {
            "type": "object",
            "required": ["left", "right"],
            "additionalProperties": False,
            "properties": {
                key: json_execution_schema(GEOMETRY_SCHEMA, media_types=("application/geo+json", "application/json"))
                for key in ("left", "right")
            },
        },
        "response": {"type": "string", "enum": ["raw", "document"]},
        "outputs": {
            "type": "object",
            "required": ["intersection"],
            "additionalProperties": False,
            "properties": {
                "intersection": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "transmissionMode": {"type": "string", "enum": ["value"]},
                        "format": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {"mediaType": {"type": "string", "enum": ["application/geo+json"]}},
                        },
                    },
                }
            },
        },
    },
}
DOCUMENT_SCHEMA = {
    "type": "object",
    "required": ["intersection"],
    "additionalProperties": False,
    "properties": {
        "intersection": {
            "type": "object",
            "required": ["value"],
            "additionalProperties": False,
            "properties": {"value": GEOMETRY_SCHEMA},
        }
    },
}


def openapi_execution():
    return {
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": deepcopy(EXECUTE_SCHEMA), "example": PROCESS_METADATA["example"]}
            },
        },
        "responses": {
            "200": {
                "description": "Raw GeoJSON geometry or intersection-keyed OGC document.",
                "content": {
                    "application/geo+json": {"schema": GEOMETRY_SCHEMA},
                    "application/json": {"schema": DOCUMENT_SCHEMA},
                },
            }
        },
    }
