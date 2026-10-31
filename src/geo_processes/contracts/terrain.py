"""Contract retaining the supplied terrain function's names and output structure."""

from copy import deepcopy

from geo_processes.contracts.files import json_execution_schema

INPUT_SCHEMAS = {
    "lat": {"type": "number", "minimum": 50, "maximum": 54},
    "lon": {"type": "number", "minimum": 3, "maximum": 8},
    "buffer_300m": {"type": "integer", "minimum": 1, "maximum": 500, "default": 300},
    "buffer_500m": {"type": "integer", "minimum": 1, "maximum": 500, "default": 500},
    "limit": {"type": "integer", "minimum": 100, "maximum": 1000, "default": 1000},
}
PERCENTAGES = [
    "pct_in_alkmaar",
    "oppervlak_lage_vegetatie_pct",
    "oppervlak_middelhoge_vegetatie_pct",
    "oppervlak_hoge_vegetatie_pct",
    "oppervlak_water_pct",
    "oppervlak_wegen_pct",
    "oppervlak_bebouwd_pct",
    "oppervlak_onverhard_pct",
    "oppervlak_onbebouwd_pct",
]
BUFFER_SCHEMA = {
    "type": "object",
    "required": PERCENTAGES,
    "additionalProperties": False,
    "properties": {key: {"type": "number"} for key in PERCENTAGES},
}
RESULT_SCHEMA = {
    "type": "object",
    "required": ["is_partial", "fetch_failures", "buffer_300m", "buffer_500m"],
    "additionalProperties": False,
    "properties": {
        "is_partial": {"type": "boolean"},
        "fetch_failures": {"type": "object", "additionalProperties": {"type": "string"}},
        "buffer_300m": BUFFER_SCHEMA,
        "buffer_500m": BUFFER_SCHEMA,
    },
}
PROCESS_METADATA = {
    "id": "terrain-analysis",
    "version": "1.0.0",
    "title": "PDOK BGT terrain analysis",
    "description": (
        "Supplied terrain algorithm with original percentages, priority masking and partial-fetch reporting. "
        "Netherlands CRS84 point, radii 1–500 metres with buffer_300m <= buffer_500m. Requires packaged "
        "Alkmaar boundary and outbound HTTPS to PDOK. Original requests have 30-second timeouts; "
        "tile subdivision has no total work bound. Prefer async for live data; worker deadline at most "
        "300 seconds. Partial results remain successful with is_partial=true."
    ),
    "jobControlOptions": ["sync-execute"],
    "outputTransmission": ["value"],
    "links": [],
    "inputs": {
        key: {"title": key, "schema": schema, "minOccurs": int(key in {"lat", "lon"}), "maxOccurs": 1}
        for key, schema in INPUT_SCHEMAS.items()
    },
    "outputs": {
        "terrain": {"title": "Terrain statistics", "schema": {**RESULT_SCHEMA, "contentMediaType": "application/json"}}
    },
    "example": {"inputs": {"lat": 52.63, "lon": 4.75, "buffer_300m": 30, "buffer_500m": 50}, "response": "document"},
}
EXECUTE_SCHEMA = {
    "type": "object",
    "required": ["inputs"],
    "additionalProperties": False,
    "properties": {
        "inputs": {
            "type": "object",
            "required": ["lat", "lon"],
            "additionalProperties": False,
            "properties": {key: json_execution_schema(schema) for key, schema in INPUT_SCHEMAS.items()},
        },
        "response": {"type": "string", "enum": ["raw", "document"]},
        "outputs": {
            "type": "object",
            "required": ["terrain"],
            "additionalProperties": False,
            "properties": {
                "terrain": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "transmissionMode": {"type": "string", "enum": ["value"]},
                        "format": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {"mediaType": {"type": "string", "enum": ["application/json"]}},
                        },
                    },
                }
            },
        },
    },
}
DOCUMENT_SCHEMA = {
    "type": "object",
    "required": ["terrain"],
    "additionalProperties": False,
    "properties": {
        "terrain": {
            "type": "object",
            "required": ["value"],
            "additionalProperties": False,
            "properties": {"value": RESULT_SCHEMA},
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
                "description": "Raw statistics or terrain-keyed OGC document.",
                "content": {"application/json": {"schema": {"oneOf": [RESULT_SCHEMA, DOCUMENT_SCHEMA]}}},
            }
        },
    }
