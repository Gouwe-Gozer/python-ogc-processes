"""OGC boundary for GeoJSON point sampling."""

from copy import deepcopy

from pygeoapi.process.base import BaseProcessor

from geo_processes.contracts.sample import GEOJSON_TYPE, JSON_TYPES, PROCESS_METADATA, openapi_execution
from geo_processes.delivery import FileOutput, format_file, output_transmission, result_base_url
from geo_processes.inputs import RasterInputError, resolve_json, resolve_source
from geo_processes.operations.sample import sample_points
from geo_processes.processes.common import integer_parameter, processing_errors, validate_band, validate_inputs
from geo_processes.storage import ResultStore


def validate_points(points):
    if isinstance(points, dict) and points.get("type") in ("Point", "MultiPoint"):
        if set(points) != {"type", "coordinates"}:
            raise RasterInputError(
                "point geometries require only type and coordinates; crs/foreign members are unsupported"
            )
        coordinates = [points["coordinates"]] if points["type"] == "Point" else points["coordinates"]
        if not isinstance(coordinates, list) or not 1 <= len(coordinates) <= 1000:
            raise RasterInputError("points requires 1–1,000 point locations")
        points = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": coordinate}}
                for coordinate in coordinates
            ],
        }
    if not isinstance(points, dict) or set(points) != {"type", "features"} or points["type"] != "FeatureCollection":
        raise RasterInputError(
            "points must be a GeoJSON Point, MultiPoint or Point FeatureCollection without crs/foreign members"
        )
    features = points["features"]
    if not isinstance(features, list) or not 1 <= len(features) <= 1000:
        raise RasterInputError("points requires 1–1,000 Point features")
    for feature in features:
        if (
            not isinstance(feature, dict)
            or set(feature) - {"type", "geometry", "properties", "id"}
            or not {"type", "geometry", "properties"} <= feature.keys()
            or feature["type"] != "Feature"
            or (feature["properties"] is not None and not isinstance(feature["properties"], dict))
            or ("id" in feature and type(feature["id"]) not in {str, int, float})
        ):
            raise RasterInputError("each point requires Feature type, Point geometry and object/null properties")
        geometry = feature["geometry"]
        if not isinstance(geometry, dict) or set(geometry) != {"type", "coordinates"} or geometry["type"] != "Point":
            raise RasterInputError("only GeoJSON Point geometries are supported")
        coordinates = geometry["coordinates"]
        if (
            not isinstance(coordinates, list)
            or len(coordinates) != 2
            or any(type(value) not in {int, float} for value in coordinates)
            or not -180 <= coordinates[0] <= 180
            or not -90 <= coordinates[1] <= 90
        ):
            raise RasterInputError("Point coordinates must be [longitude, latitude] within WGS84 bounds")
    return points


class RasterSamplePointsProcessor(BaseProcessor):
    result_extension = "geojson"

    def __init__(self, processor_def):
        super().__init__(processor_def, deepcopy(PROCESS_METADATA))
        self.supports_outputs = True
        self.result_base_url = ""

    def execute(self, data, outputs=None):
        validate_inputs(data, allowed={"source", "points", "band"}, required={"source", "points"})
        transmission = output_transmission(outputs, media_type=GEOJSON_TYPE)
        if transmission == "reference":
            result_base_url(self.result_base_url)
        with processing_errors():
            points = validate_points(resolve_json(data["points"], name="points", media_types=JSON_TYPES))
            band = integer_parameter(data.get("band", 1), "band")
            store = ResultStore.from_environment()
            with resolve_source(data["source"], require_crs=True) as path:
                validate_band(path, band)
                result = store.publish(lambda output: sample_points(path, output, points, band), extension="geojson")
        return GEOJSON_TYPE, FileOutput(result, transmission, store, "geojson")

    def format_result(self, value, response):
        return format_file(value, response, self.result_base_url)

    openapi_execution = staticmethod(openapi_execution)
