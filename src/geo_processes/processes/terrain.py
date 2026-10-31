"""Adapt the supplied terrain function without introducing FROST integration."""

import math
from copy import deepcopy

from pygeoapi.process.base import BaseProcessor

from geo_processes.contracts.terrain import INPUT_SCHEMAS, PROCESS_METADATA, openapi_execution
from geo_processes.delivery import output_transmission
from geo_processes.errors import InvalidExecutionRequestError
from geo_processes.inputs import resolve_json
from geo_processes.processes.common import processing_errors, validate_inputs


class TerrainAnalysisProcessor(BaseProcessor):
    def __init__(self, processor_def):
        super().__init__(processor_def, deepcopy(PROCESS_METADATA))
        self.supports_outputs = True

    def execute(self, data, outputs=None):
        validate_inputs(data, allowed=set(INPUT_SCHEMAS), required={"lat", "lon"})
        if output_transmission(outputs, output_id="terrain", media_type="application/json") != "value":
            raise InvalidExecutionRequestError("terrain supports only value transmission")
        parameters = {}
        with processing_errors():
            for name, schema in INPUT_SCHEMAS.items():
                value = resolve_json(data.get(name, schema.get("default")), name=name)
                types = {int} if schema["type"] == "integer" else {int, float}
                if (
                    type(value) not in types
                    or not schema["minimum"] <= value <= schema["maximum"]
                    or not math.isfinite(value)
                ):
                    raise InvalidExecutionRequestError(
                        f"{name} must be {schema['type']} in [{schema['minimum']}, {schema['maximum']}]"
                    )
                parameters[name] = value
        if parameters["buffer_300m"] > parameters["buffer_500m"]:
            raise InvalidExecutionRequestError("buffer_300m must not exceed buffer_500m")
        # The original module initializes CRS transformers. Load it only when
        # executing, so registration/discovery do not load data or contact PDOK.
        from geo_processes.operations.terrain import get_terrain_analysis

        return "application/json", get_terrain_analysis(**parameters)

    @staticmethod
    def format_result(value, response):
        return {"terrain": {"value": value}} if response == "document" else value

    openapi_execution = staticmethod(openapi_execution)
