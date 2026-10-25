"""OGC boundary for approved, bounded raster reprojection."""

from collections.abc import Mapping
from copy import deepcopy

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError

from geo_processes import engine
from geo_processes.contracts.warp import (
    DOCUMENT_SCHEMA,
    EXECUTE_SCHEMA,
    PROCESS_METADATA,
    RESAMPLING_METHODS,
    TARGET_CRSS,
    TIFF_TYPE,
)
from geo_processes.delivery import FileOutput, ResultCapacityError, format_file, output_transmission, result_base_url
from geo_processes.errors import InputBusyError, InputTooLargeError, InvalidExecutionRequestError
from geo_processes.inputs import (
    RasterInputBusyError,
    RasterInputError,
    RasterInputTooLargeError,
    resolve_scalar,
    resolve_source,
    validate_source,
)
from geo_processes.storage import (
    ResultStore,
    ResultStoreBusyError,
    ResultStoreError,
    ResultStoreFullError,
)


class RasterWarpProcessor(BaseProcessor):
    result_extension = "tif"

    def __init__(self, processor_def):
        super().__init__(processor_def, deepcopy(PROCESS_METADATA))
        self.supports_outputs = True
        self.result_base_url = ""

    def execute(self, data, outputs=None):
        if not isinstance(data, Mapping) or set(data) - {"source", "target_crs", "resampling"}:
            raise InvalidExecutionRequestError("inputs must contain only source, target_crs and resampling")
        source, target, resampling = data.get("source"), data.get("target_crs"), data.get("resampling", "bilinear")
        transmission = self._transmission(outputs)
        if transmission == "reference":
            self._base_url()
        try:
            validate_source(source)
            target = resolve_scalar(target, name="target_crs", choices=TARGET_CRSS)
            resampling = resolve_scalar(resampling, name="resampling", choices=RESAMPLING_METHODS)
            store = ResultStore.from_environment()
            with resolve_source(source, require_crs=True) as path:
                result = store.publish(lambda output: engine.warp_raster(path, output, target, resampling))
        except RasterInputTooLargeError as error:
            raise InputTooLargeError(user_msg=str(error)) from error
        except RasterInputError as error:
            raise InvalidExecutionRequestError(str(error)) from error
        except RasterInputBusyError as error:
            raise InputBusyError(user_msg=str(error)) from error
        except (ResultStoreBusyError, ResultStoreFullError) as error:
            raise ResultCapacityError(user_msg=str(error)) from error
        except (engine.RasterWarpError, ResultStoreError, OSError) as error:
            raise ProcessorExecuteError(user_msg="raster output could not be created") from error
        return TIFF_TYPE, FileOutput(result, transmission, store)

    @staticmethod
    def _transmission(outputs):
        return output_transmission(outputs)

    def _base_url(self):
        return result_base_url(self.result_base_url)

    def format_result(self, value, response):
        return format_file(value, response, self.result_base_url)

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
                    "description": "GeoTIFF bytes (raw/value), or a reference/base64 results mapping (document).",
                    "content": {
                        TIFF_TYPE: {"schema": {"type": "string", "format": "binary"}},
                        "application/json": {"schema": DOCUMENT_SCHEMA},
                    },
                },
                "204": {
                    "description": "Raw/reference: empty body and Link to the GeoTIFF.",
                    "headers": {"Link": {"schema": {"type": "string"}, "description": "Result URL and media type"}},
                },
                "503": {
                    "description": "Temporary input capacity, the warp writer or bounded result storage is busy/full.",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
            },
        }
