"""Use existing bounded staging and file delivery for all-band conversion."""

from copy import deepcopy

from pygeoapi.process.base import BaseProcessor

from geo_processes.contracts.convert_dtype import INPUT_SCHEMAS, PROCESS_METADATA, openapi_execution
from geo_processes.delivery import FileOutput, format_file, output_transmission, result_base_url
from geo_processes.errors import InvalidExecutionRequestError
from geo_processes.inputs import resolve_json, resolve_source
from geo_processes.processes.common import processing_errors, validate_inputs
from geo_processes.storage import ResultStore


class RasterConvertDtypeProcessor(BaseProcessor):
    result_extension = "tif"

    def __init__(self, processor_def):
        super().__init__(processor_def, deepcopy(PROCESS_METADATA))
        self.supports_outputs = True
        self.result_base_url = ""

    def execute(self, data, outputs=None):
        from geo_processes.operations.convert_dtype import convert_dtype

        validate_inputs(data, allowed={"source", *INPUT_SCHEMAS}, required={"source", "dtype"})
        transmission = output_transmission(outputs)
        if transmission == "reference":
            result_base_url(self.result_base_url)
        parameters = {}
        with processing_errors():
            for key, schema in INPUT_SCHEMAS.items():
                value = resolve_json(data.get(key, schema.get("default")), name=key)
                if key == "nodata":
                    if key not in data:
                        continue
                    valid = type(value) in {int, float} and -1.7976931348623157e308 <= value <= 1.7976931348623157e308
                else:
                    valid = isinstance(value, str) and value in schema["enum"]
                if not valid:
                    raise InvalidExecutionRequestError(f"invalid {key} value")
                parameters[key] = value
            store = ResultStore.from_environment()
            with resolve_source(data["source"], require_crs=False) as path:
                try:
                    result = store.publish(lambda output: convert_dtype(path, output, **parameters))
                except ValueError as error:
                    raise InvalidExecutionRequestError(str(error)) from error
        return "image/tiff", FileOutput(result, transmission, store)

    def format_result(self, value, response):
        return format_file(value, response, self.result_base_url)

    openapi_execution = staticmethod(openapi_execution)
