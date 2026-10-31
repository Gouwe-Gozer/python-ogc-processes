"""Expose independently written Python code using pygeoapi's BaseProcessor."""

from copy import deepcopy

from pygeoapi.process.base import BaseProcessor

from custom_processes.contract import DOCUMENT_SCHEMA, EXECUTE_SCHEMA, PROCESS_METADATA, STATISTICS_SCHEMA
from custom_processes.operation import text_statistics
from geo_processes.delivery import output_transmission
from geo_processes.errors import InvalidExecutionRequestError
from geo_processes.inputs import resolve_json
from geo_processes.processes.common import processing_errors, validate_inputs


class TextStatisticsProcessor(BaseProcessor):
    def __init__(self, processor_def):
        super().__init__(processor_def, deepcopy(PROCESS_METADATA))
        self.supports_outputs = True

    def execute(self, data, outputs=None):
        validate_inputs(data, allowed={"text"}, required={"text"})
        if output_transmission(outputs, output_id="statistics", media_type="application/json") != "value":
            raise InvalidExecutionRequestError("statistics supports only value transmission")
        with processing_errors():
            text = resolve_json(data["text"], name="text")
        if not isinstance(text, str) or len(text) > 4096:
            raise InvalidExecutionRequestError("text must be a string of at most 4096 characters")
        return "application/json", text_statistics(text)

    @staticmethod
    def format_result(value, response):
        return {"statistics": {"value": value}} if response == "document" else value

    @staticmethod
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
                    "description": "Raw statistics or an OGC statistics-keyed document.",
                    "content": {"application/json": {"schema": {"oneOf": [STATISTICS_SCHEMA, DOCUMENT_SCHEMA]}}},
                }
            },
        }
