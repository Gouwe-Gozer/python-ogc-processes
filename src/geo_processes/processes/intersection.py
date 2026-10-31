"""Direct pygeoapi boundary for the opt-in Shapely process."""

from copy import deepcopy

from pygeoapi.process.base import BaseProcessor

from geo_processes.contracts.intersection import PROCESS_METADATA, openapi_execution
from geo_processes.delivery import output_transmission
from geo_processes.errors import InvalidExecutionRequestError
from geo_processes.inputs import resolve_json
from geo_processes.processes.common import processing_errors, validate_inputs
from geo_processes.responses import ProcessResponse


class GeometryIntersectionProcessor(BaseProcessor):
    def __init__(self, processor_def):
        super().__init__(processor_def, deepcopy(PROCESS_METADATA))
        self.supports_outputs = True

    def execute(self, data, outputs=None):
        from geo_processes.operations.intersection import geometry_intersection

        validate_inputs(data, allowed={"left", "right"}, required={"left", "right"})
        if output_transmission(outputs, output_id="intersection", media_type="application/geo+json") != "value":
            raise InvalidExecutionRequestError("intersection supports only value transmission")
        with processing_errors():
            values = [
                resolve_json(data[key], name=key, media_types=("application/geo+json", "application/json"))
                for key in ("left", "right")
            ]
        try:
            return "application/geo+json", geometry_intersection(*values)
        except ValueError as error:
            raise InvalidExecutionRequestError(str(error)) from error

    @staticmethod
    def format_result(value, response):
        if response == "document":
            return ProcessResponse({"intersection": {"value": value}}, "application/json")
        return value

    openapi_execution = staticmethod(openapi_execution)
