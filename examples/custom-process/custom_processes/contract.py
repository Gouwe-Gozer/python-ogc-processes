"""Explicit OGC metadata and JSON contracts for this example only."""

from geo_processes.contracts.files import json_execution_schema

TEXT_SCHEMA = {"type": "string", "maxLength": 4096}
STATISTICS_SCHEMA = {
    "type": "object",
    "required": ["characters", "words"],
    "additionalProperties": False,
    "properties": {name: {"type": "integer", "minimum": 0} for name in ("characters", "words")},
}
PROCESS_METADATA = {
    "id": "text-statistics",
    "version": "1.0.0",
    "title": "Text statistics",
    "description": "Count characters and whitespace-separated words in at most 4096 Unicode characters.",
    "jobControlOptions": ["sync-execute"],
    "outputTransmission": ["value"],
    "links": [],
    "inputs": {"text": {"title": "Text", "schema": TEXT_SCHEMA, "minOccurs": 1, "maxOccurs": 1}},
    "outputs": {
        "statistics": {
            "title": "Text statistics",
            "schema": {**STATISTICS_SCHEMA, "contentMediaType": "application/json"},
        }
    },
    "example": {"inputs": {"text": "Bring your own Python!"}, "response": "document"},
}
OUTPUT_OPTIONS = {
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
EXECUTE_SCHEMA = {
    "type": "object",
    "required": ["inputs"],
    "additionalProperties": False,
    "properties": {
        "inputs": {
            "type": "object",
            "required": ["text"],
            "additionalProperties": False,
            "properties": {"text": json_execution_schema(TEXT_SCHEMA)},
        },
        "response": {"type": "string", "enum": ["raw", "document"]},
        "outputs": {
            "type": "object",
            "required": ["statistics"],
            "additionalProperties": False,
            "properties": {"statistics": OUTPUT_OPTIONS},
        },
    },
}
DOCUMENT_SCHEMA = {
    "type": "object",
    "required": ["statistics"],
    "additionalProperties": False,
    "properties": {
        "statistics": {
            "type": "object",
            "required": ["value"],
            "additionalProperties": False,
            "properties": {"value": STATISTICS_SCHEMA},
        }
    },
}
