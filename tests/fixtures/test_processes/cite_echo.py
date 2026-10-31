"""Bounded, validation-only echo through the ordinary processor interfaces."""

import json
import time
from collections.abc import Mapping
from copy import deepcopy
from email.message import EmailMessage
from email.policy import SMTP

from jsonschema import Draft7Validator
from pygeoapi.process.base import BaseProcessor

from geo_processes.contracts.files import json_execution_schema
from geo_processes.delivery import output_transmission
from geo_processes.errors import InvalidExecutionRequestError
from geo_processes.inputs import resolve_json
from geo_processes.processes.common import processing_errors, validate_inputs
from geo_processes.responses import ProcessResponse

PAUSE_SCHEMA = {"type": "integer", "minimum": 0, "maximum": 5, "default": 0}
VALUE_SCHEMAS = {
    "message": {"type": "string", "maxLength": 4096},
    # The pinned ETS flattens array item types; integers avoid its string-as-array generator bug.
    "array": {
        "type": "array",
        "items": {"type": "integer", "minimum": -1000000, "maximum": 1000000},
        "maxItems": 16,
        "default": [],
    },
    # Keep an application-object choice before bbox for the ETS generic object generator.
    "mixed": {
        "oneOf": [
            {"type": "string", "maxLength": 4096, "contentMediaType": "application/json"},
            {"type": "integer", "minimum": -1000000, "maximum": 1000000},
            {
                "type": "object",
                "required": ["label"],
                "additionalProperties": False,
                "properties": {"label": {"type": "string", "maxLength": 4096}},
            },
        ],
        "default": "",
    },
    "bbox": {
        "type": "object",
        "required": ["bbox"],
        "additionalProperties": False,
        "properties": {
            "bbox": {
                "type": "array",
                "items": {"type": "number"},
                "oneOf": [{"minItems": 4, "maxItems": 4}, {"minItems": 6, "maxItems": 6}],
            },
            "crs": {
                "type": "string",
                "enum": [
                    "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                    "http://www.opengis.net/def/crs/OGC/0/CRS84h",
                    "urn:ogc:def:crs:EPSG:6.6:4326",
                ],
            },
        },
        "default": {"bbox": [0, 0, 0, 0]},
    },
}
INPUT_SCHEMAS = {**VALUE_SCHEMAS, "pause": PAUSE_SCHEMA}
PROCESS_METADATA = {
    "version": "1.0.0",
    "id": "cite-echo",
    "title": "CITE echo fixture",
    "description": "Test-only bounded JSON echo; optional inputs have defaults and pause is a control input.",
    "jobControlOptions": ["sync-execute"],
    "outputTransmission": ["value"],
    "inputs": {
        name: {"title": name, "schema": schema, "minOccurs": int(name == "message"), "maxOccurs": 1}
        for name, schema in INPUT_SCHEMAS.items()
    },
    "outputs": {
        name: {"title": name, "schema": {**schema, "contentMediaType": "application/json"}}
        for name, schema in VALUE_SCHEMAS.items()
    },
}


class CiteEchoProcessor(BaseProcessor):
    def __init__(self, processor_def):
        super().__init__(processor_def, deepcopy(PROCESS_METADATA))
        self.supports_outputs = True

    def execute(self, data, outputs=None):
        validate_inputs(data, allowed=set(INPUT_SCHEMAS), required={"message"})
        values = {}
        with processing_errors():
            for name, schema in INPUT_SCHEMAS.items():
                value = data.get(name, deepcopy(schema.get("default")))
                # Core permits an unqualified bounding box; application objects still use qualified values.
                if name == "bbox" and isinstance(value, Mapping) and "bbox" in value:
                    value = {"value": value}
                value = resolve_json(value, name=name)
                if not Draft7Validator(schema).is_valid(value):
                    raise InvalidExecutionRequestError(f"{name} does not match its declared echo schema")
                values[name] = value
        if outputs is not None and (not isinstance(outputs, Mapping) or set(outputs) - set(VALUE_SCHEMAS)):
            raise InvalidExecutionRequestError("outputs must select defined echo outputs")
        selected = outputs or {name: {} for name in VALUE_SCHEMAS}
        for name, options in selected.items():
            if output_transmission({name: options}, output_id=name, media_type="application/json") != "value":
                raise InvalidExecutionRequestError("echo supports only value transmission")
        if values["pause"]:
            time.sleep(values["pause"])
        return "application/json", {name: values[name] for name in selected}

    @staticmethod
    def format_result(values, response):
        if response == "document":
            return {name: {"value": value} for name, value in values.items()}
        if len(values) == 1:
            return next(iter(values.values()))
        # Multiple raw outputs require one MIME part per output (Core requirement 29).
        multipart = EmailMessage(policy=SMTP)
        multipart.set_type("multipart/related")
        multipart.set_param("type", "application/json")
        for name, value in values.items():
            part = EmailMessage(policy=SMTP)
            part["Content-Type"] = "application/json"
            part["Content-ID"] = name
            part.set_payload(json.dumps(value, allow_nan=False))
            multipart.attach(part)
        body = multipart.as_bytes().split(b"\r\n\r\n", 1)[1]
        return ProcessResponse(body, str(multipart["Content-Type"]))

    @staticmethod
    def openapi_execution():
        wire_inputs = {name: json_execution_schema(schema) for name, schema in INPUT_SCHEMAS.items()}
        wire_inputs["bbox"]["oneOf"].append(VALUE_SCHEMAS["bbox"])
        # Application objects require qualified values; only scalar mixed choices can be bare.
        wire_inputs["mixed"]["oneOf"][-1] = {
            "oneOf": [schema for schema in VALUE_SCHEMAS["mixed"]["oneOf"] if schema["type"] != "object"]
        }
        output_options = {
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
        document = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                name: {"type": "object", "required": ["value"], "properties": {"value": schema}}
                for name, schema in VALUE_SCHEMAS.items()
            },
        }
        return {
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["inputs"],
                            "additionalProperties": False,
                            "properties": {
                                "inputs": {
                                    "type": "object",
                                    "required": ["message"],
                                    "additionalProperties": False,
                                    "properties": wire_inputs,
                                },
                                "response": {"type": "string", "enum": ["raw", "document"]},
                                "outputs": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {name: deepcopy(output_options) for name in VALUE_SCHEMAS},
                                },
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Selected JSON value, OGC result document, or multipart raw outputs.",
                    "content": {
                        "application/json": {"schema": {"anyOf": [*VALUE_SCHEMAS.values(), document]}},
                        "multipart/related": {"schema": {"type": "string", "format": "binary"}},
                    },
                }
            },
        }
