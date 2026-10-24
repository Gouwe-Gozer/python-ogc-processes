"""Small schema builders for the existing single-file output convention."""

from copy import deepcopy

from geo_processes import __version__
from geo_processes.contracts.sources import LINK_METADATA, MAX_URL_LENGTH, SOURCE_EXECUTE_SCHEMA, SOURCE_VALUE_SCHEMA

BAND_SCHEMA = {"type": "integer", "minimum": 1, "default": 1}


def json_execution_schema(schema, *, media_types=("application/json",)):
    qualified = {
        "type": "object",
        "required": ["value"],
        "additionalProperties": False,
        "properties": {"value": schema, "mediaType": {"type": "string", "enum": list(media_types)}},
    }
    reference = {
        "type": "object",
        "required": ["href"],
        "additionalProperties": False,
        "properties": {
            "href": {"type": "string", "pattern": "^https://", "maxLength": MAX_URL_LENGTH},
            "type": {"type": "string", "enum": list(media_types)},
            **{key: {"type": "string"} for key in sorted(LINK_METADATA)},
        },
    }
    return {"oneOf": [qualified, reference] + ([] if schema.get("type") == "object" else [schema])}


def metadata(identifier, title, description, inputs, media_type, output_schema, example):
    from geo_processes.contracts.sources import SOURCE_DESCRIPTION

    return {
        "id": identifier,
        "version": __version__,
        "title": title,
        "description": description,
        "keywords": ["Rasterio", "raster"],
        "jobControlOptions": ["sync-execute"],
        "outputTransmission": ["value", "reference"],
        "inputs": {
            "source": {
                "title": "Source GeoTIFF",
                "description": SOURCE_DESCRIPTION,
                "schema": SOURCE_VALUE_SCHEMA,
                "minOccurs": 1,
                "maxOccurs": 1,
            },
            "band": {
                "title": "Band",
                "description": "One-based source band index.",
                "schema": BAND_SCHEMA,
                "minOccurs": 0,
                "maxOccurs": 1,
            },
            **inputs,
        },
        "outputs": {"result": {"title": title, "schema": {**output_schema, "contentMediaType": media_type}}},
        "example": {
            "inputs": {"source": {"href": "https://data.example.org/raster.tif", "type": "image/tiff"}, **example}
        },
    }


def execution_contract(process, media_type, output_schema, wire_inputs):
    output_options = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "transmissionMode": {"type": "string", "enum": ["value", "reference"]},
            "format": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"mediaType": {"type": "string", "enum": [media_type]}},
            },
        },
    }
    schema = {
        "type": "object",
        "required": ["inputs"],
        "additionalProperties": False,
        "properties": {
            "inputs": {
                "type": "object",
                "additionalProperties": False,
                "required": [key for key, item in process["inputs"].items() if item["minOccurs"] == 1],
                "properties": {
                    "source": SOURCE_EXECUTE_SCHEMA,
                    "band": json_execution_schema(BAND_SCHEMA),
                    **wire_inputs,
                },
            },
            "response": {"type": "string", "enum": ["raw", "document"]},
            "outputs": {
                "type": "object",
                "required": ["result"],
                "additionalProperties": False,
                "properties": {"result": output_options},
            },
        },
    }
    inline = {
        "type": "object",
        "required": ["value", "mediaType"],
        "additionalProperties": False,
        "properties": {"value": output_schema, "mediaType": {"type": "string", "enum": [media_type]}},
    }
    if media_type == "image/tiff":
        inline["required"].append("encoding")
        inline["properties"]["value"] = {"type": "string", "format": "byte"}
        inline["properties"]["encoding"] = {"type": "string", "enum": ["base64"]}
    reference = {
        "type": "object",
        "required": ["href", "type"],
        "additionalProperties": False,
        "properties": {"href": {"type": "string", "format": "uri"}, "type": {"type": "string", "enum": [media_type]}},
    }
    document = {
        "type": "object",
        "required": ["result"],
        "additionalProperties": False,
        "properties": {"result": {"oneOf": [inline, reference]}},
    }
    responses = {media_type: {"schema": output_schema}}
    responses["application/json"] = {"schema": document}
    return {
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": deepcopy(schema), "example": process["example"]}},
        },
        "responses": {
            "200": {
                "description": "Native output (raw/value) or OGC result document (document).",
                "content": responses,
            },
            "204": {
                "description": "Raw/reference: empty body and Link to the stored result.",
                "headers": {"Link": {"schema": {"type": "string"}}},
            },
        },
    }
