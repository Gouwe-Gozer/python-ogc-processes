"""Test-only echo using the public application's processor interface."""

from copy import deepcopy

from pygeoapi.process.base import BaseProcessor

from geo_processes.contracts.files import json_execution_schema
from geo_processes.delivery import output_transmission
from geo_processes.errors import InvalidExecutionRequestError
from geo_processes.inputs import resolve_json
from geo_processes.processes.common import processing_errors, validate_inputs

PROCESS_METADATA = {
    "version": "1.0.0",
    "id": "cite-echo",
    "title": "CITE echo fixture",
    "description": "Test-only string echo through the ordinary application manager and response formatter.",
    "jobControlOptions": ["sync-execute"],
    "outputTransmission": ["value"],
    "inputs": {
        "message": {"title": "Message", "schema": {"type": "string"}, "minOccurs": 1, "maxOccurs": 1},
    },
    "outputs": {
        "message": {
            "title": "Echoed message",
            "schema": {"type": "string", "contentMediaType": "application/json"},
        }
    },
}


class CiteEchoProcessor(BaseProcessor):
    def __init__(self, processor_def):
        super().__init__(processor_def, deepcopy(PROCESS_METADATA))
        self.supports_outputs = True

    def execute(self, data, outputs=None):
        validate_inputs(data, allowed={"message"}, required={"message"})
        if output_transmission(outputs, output_id="message", media_type="application/json") != "value":
            raise InvalidExecutionRequestError("echo supports only value transmission")
        with processing_errors():
            message = resolve_json(data["message"], name="message")
        if not isinstance(message, str):
            raise InvalidExecutionRequestError("message must be a string")
        return "application/json", message

    @staticmethod
    def format_result(value, response):
        if response == "document":
            return {"message": {"value": value}}
        return value

    @staticmethod
    def openapi_execution():
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
                                    "properties": {"message": json_execution_schema({"type": "string"})},
                                },
                                "response": {"type": "string", "enum": ["raw", "document"]},
                                "outputs": {
                                    "type": "object",
                                    "required": ["message"],
                                    "additionalProperties": False,
                                    "properties": {
                                        "message": {
                                            "type": "object",
                                            "properties": {
                                                "transmissionMode": {"type": "string", "enum": ["value"]},
                                                "format": {
                                                    "type": "object",
                                                    "properties": {"mediaType": {"enum": ["application/json"]}},
                                                },
                                            },
                                        }
                                    },
                                },
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "JSON string (raw) or qualified message (document).",
                    "content": {
                        "application/json": {
                            "schema": {
                                "oneOf": [
                                    {"type": "string"},
                                    {
                                        "type": "object",
                                        "required": ["message"],
                                        "additionalProperties": False,
                                        "properties": {
                                            "message": {
                                                "type": "object",
                                                "required": ["value"],
                                                "properties": {"value": {"type": "string"}},
                                            }
                                        },
                                    },
                                ]
                            }
                        }
                    },
                }
            },
        }
