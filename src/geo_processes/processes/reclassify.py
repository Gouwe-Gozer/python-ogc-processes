"""OGC boundary for a bounded, one-band classification."""

from copy import deepcopy

from pygeoapi.process.base import BaseProcessor

from geo_processes.contracts.reclassify import PROCESS_METADATA, openapi_execution
from geo_processes.delivery import FileOutput, format_file, output_transmission, result_base_url
from geo_processes.inputs import RasterInputError, resolve_json, resolve_source
from geo_processes.operations.reclassify import NODATA, reclassify
from geo_processes.processes.common import integer_parameter, processing_errors, validate_band, validate_inputs
from geo_processes.storage import ResultStore


def validate_classes(classes):
    if not isinstance(classes, list) or not 1 <= len(classes) <= 128:
        raise RasterInputError("classes must be an array of 1–128 {min, max, value} intervals")
    for item in classes:
        if (
            not isinstance(item, dict)
            or set(item) != {"min", "max", "value"}
            or type(item["min"]) not in {int, float}
            or type(item["max"]) not in {int, float}
            or item["min"] >= item["max"]
            or type(item["value"]) is not int
            or not NODATA < item["value"] <= 2147483647
        ):
            raise RasterInputError("classes require min < max and int32 values excluding nodata (-2147483648)")
    ordered = sorted(classes, key=lambda item: item["min"])
    if any(left["max"] > right["min"] for left, right in zip(ordered, ordered[1:], strict=False)):
        raise RasterInputError("classification intervals must not overlap")
    return ordered


class RasterReclassifyProcessor(BaseProcessor):
    result_extension = "tif"

    def __init__(self, processor_def):
        super().__init__(processor_def, deepcopy(PROCESS_METADATA))
        self.supports_outputs = True
        self.result_base_url = ""

    def execute(self, data, outputs=None):
        validate_inputs(data, allowed={"source", "classes", "band"}, required={"source", "classes"})
        transmission = output_transmission(outputs)
        if transmission == "reference":
            result_base_url(self.result_base_url)
        with processing_errors():
            classes = validate_classes(resolve_json(data["classes"], name="classes"))
            band = integer_parameter(data.get("band", 1), "band")
            store = ResultStore.from_environment()
            with resolve_source(data["source"]) as path:
                validate_band(path, band)
                result = store.publish(lambda output: reclassify(path, output, classes, band))
        return "image/tiff", FileOutput(result, transmission, store)

    def format_result(self, value, response):
        return format_file(value, response, self.result_base_url)

    openapi_execution = staticmethod(openapi_execution)
