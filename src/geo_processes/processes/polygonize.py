"""OGC boundary for categorical GeoTIFF polygonization."""

from copy import deepcopy

from pygeoapi.process.base import BaseProcessor

from geo_processes.contracts.geojson import GEOJSON_TYPE
from geo_processes.contracts.polygonize import PROCESS_METADATA, openapi_execution
from geo_processes.delivery import FileOutput, format_file, output_transmission, result_base_url
from geo_processes.inputs import resolve_source
from geo_processes.operations.polygonize import polygonize
from geo_processes.processes.common import integer_parameter, processing_errors, validate_band, validate_inputs
from geo_processes.storage import ResultStore


class RasterPolygonizeProcessor(BaseProcessor):
    result_extension = "geojson"

    def __init__(self, processor_def):
        super().__init__(processor_def, deepcopy(PROCESS_METADATA))
        self.supports_outputs = True
        self.result_base_url = ""

    def execute(self, data, outputs=None):
        validate_inputs(data, allowed={"source", "band", "connectivity"}, required={"source"})
        transmission = output_transmission(outputs, media_type=GEOJSON_TYPE)
        if transmission == "reference":
            result_base_url(self.result_base_url)
        with processing_errors():
            band = integer_parameter(data.get("band", 1), "band")
            connectivity = integer_parameter(data.get("connectivity", 4), "connectivity", choices=[4, 8])
            store = ResultStore.from_environment()
            with resolve_source(data["source"], require_crs=True) as path:
                validate_band(path, band)
                result = store.publish(lambda output: polygonize(path, output, band, connectivity), extension="geojson")
        return GEOJSON_TYPE, FileOutput(result, transmission, store, "geojson")

    def format_result(self, value, response):
        return format_file(value, response, self.result_base_url)

    openapi_execution = staticmethod(openapi_execution)
