"""OGC boundary for the bounded raster-info operation."""

from collections.abc import Mapping
from copy import deepcopy

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError

from geo_processes import engine
from geo_processes.contracts.info import DOCUMENT_SCHEMA, EXECUTE_SCHEMA, INFO_SCHEMA, PROCESS_METADATA
from geo_processes.errors import InputBusyError, InputTooLargeError, InvalidExecutionRequestError
from geo_processes.inputs import (
    RasterInputBusyError,
    RasterInputError,
    RasterInputTooLargeError,
    resolve_source,
    validate_source,
)


class RasterInfoProcessor(BaseProcessor):
    """Inspect a bounded user-supplied GeoTIFF."""

    def __init__(self, processor_def):
        # Upstream OpenAPI generation pops contentMediaType from metadata.
        super().__init__(processor_def, deepcopy(PROCESS_METADATA))
        self.supports_outputs = True

    def execute(self, data, outputs=None):
        if not isinstance(data, Mapping):
            raise InvalidExecutionRequestError("inputs must be an object")
        if set(data) - {"source"}:
            raise InvalidExecutionRequestError("unsupported input identifier")
        source = data.get("source")
        self._validate_outputs(outputs)
        try:
            validate_source(source)
            with resolve_source(source) as path:
                info = engine.raster_info(path)
        except RasterInputTooLargeError as error:
            raise InputTooLargeError(user_msg=str(error)) from error
        except RasterInputError as error:
            raise InvalidExecutionRequestError(str(error)) from error
        except RasterInputBusyError as error:
            raise InputBusyError(user_msg=str(error)) from error
        except engine.RasterInfoError as error:
            raise ProcessorExecuteError(user_msg="configured raster could not be inspected") from error
        return "application/json", info

    @staticmethod
    def _validate_outputs(outputs):
        if outputs is None:
            return
        if not isinstance(outputs, Mapping) or set(outputs) != {"info"}:
            raise InvalidExecutionRequestError("outputs must select the defined info output")
        options = outputs["info"]
        if not isinstance(options, Mapping) or set(options) - {"transmissionMode", "format"}:
            raise InvalidExecutionRequestError("unsupported info output options")
        if options.get("transmissionMode", "value") != "value":
            raise InvalidExecutionRequestError("info supports only value transmission")
        output_format = options.get("format", {})
        if not isinstance(output_format, Mapping) or set(output_format) - {"mediaType"}:
            raise InvalidExecutionRequestError("unsupported info output format")
        if output_format.get("mediaType", "application/json") != "application/json":
            raise InvalidExecutionRequestError("info supports only application/json")

    @staticmethod
    def format_result(value, response):
        """Encode this operation's one JSON output using OGC results.yaml."""
        return {"info": {"value": value}} if response == "document" else value

    @staticmethod
    def openapi_execution():
        """Describe the execution choices this particular operation supports."""
        return {
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {"schema": deepcopy(EXECUTE_SCHEMA), "example": PROCESS_METADATA["example"]}
                },
            },
            "responses": {
                "503": {
                    "description": "Temporary input capacity is busy",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "200": {
                    "description": "Application-defined raster information (raw) or an info-keyed document (document).",
                    "content": {"application/json": {"schema": {"oneOf": [INFO_SCHEMA, DOCUMENT_SCHEMA]}}},
                },
            },
        }
