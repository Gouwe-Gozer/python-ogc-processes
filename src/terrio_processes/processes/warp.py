"""OGC boundary for approved, bounded raster reprojection."""

import base64
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from urllib.parse import urlsplit

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError

from terrio_processes import engine
from terrio_processes.contracts.warp import (
    DOCUMENT_SCHEMA,
    EXECUTE_SCHEMA,
    PROCESS_METADATA,
    RESAMPLING_METHODS,
    TARGET_CRSS,
    TIFF_TYPE,
)
from terrio_processes.datasets import DATASETS
from terrio_processes.manager import InvalidExecutionRequestError
from terrio_processes.responses import ProcessResponse
from terrio_processes.storage import (
    ResultStore,
    ResultStoreBusyError,
    ResultStoreError,
    ResultStoreFullError,
    StoredResult,
)


class ResultCapacityError(ProcessorExecuteError):
    """A bounded local service currently cannot accept another raster."""

    http_status_code = 503
    ogc_exception_code = "ServerBusy"


@dataclass(frozen=True)
class WarpOutput:
    result: StoredResult
    transmission: str
    store: ResultStore


class TerrioWarpProcessor(BaseProcessor):
    def __init__(self, processor_def):
        super().__init__(processor_def, deepcopy(PROCESS_METADATA))
        self.supports_outputs = True
        self.result_base_url = ""

    def execute(self, data, outputs=None):
        if not isinstance(data, Mapping) or set(data) - {"source", "target_crs", "resampling"}:
            raise InvalidExecutionRequestError("inputs must contain only source, target_crs and resampling")
        source, target, resampling = data.get("source"), data.get("target_crs"), data.get("resampling", "bilinear")
        if not isinstance(source, str) or source not in DATASETS:
            raise InvalidExecutionRequestError("source must be a published dataset identifier: demo-dem")
        if not isinstance(target, str) or target not in TARGET_CRSS:
            raise InvalidExecutionRequestError("target_crs must be EPSG:28992, EPSG:4326 or EPSG:3857")
        if not isinstance(resampling, str) or resampling not in RESAMPLING_METHODS:
            raise InvalidExecutionRequestError("resampling must be nearest or bilinear")
        transmission = self._transmission(outputs)
        if transmission == "reference":
            self._base_url()
        try:
            store = ResultStore.from_environment()
            result = store.publish(lambda output: engine.warp_raster(DATASETS[source], output, target, resampling))
        except (ResultStoreBusyError, ResultStoreFullError) as error:
            raise ResultCapacityError(user_msg=str(error)) from error
        except (engine.RasterWarpError, ResultStoreError, OSError) as error:
            raise ProcessorExecuteError(user_msg="raster output could not be created") from error
        return TIFF_TYPE, WarpOutput(result, transmission, store)

    @staticmethod
    def _transmission(outputs):
        if outputs is None:
            return "value"
        if not isinstance(outputs, Mapping) or set(outputs) != {"result"}:
            raise InvalidExecutionRequestError("outputs must select the defined result output")
        options = outputs["result"]
        if not isinstance(options, Mapping) or set(options) - {"transmissionMode", "format"}:
            raise InvalidExecutionRequestError("unsupported result output options")
        mode = options.get("transmissionMode", "value")
        if not isinstance(mode, str) or mode not in {"value", "reference"}:
            raise InvalidExecutionRequestError("result transmissionMode must be value or reference")
        output_format = options.get("format", {})
        if not isinstance(output_format, Mapping) or set(output_format) - {"mediaType"}:
            raise InvalidExecutionRequestError("unsupported result output format")
        if output_format.get("mediaType", TIFF_TYPE) != TIFF_TYPE:
            raise InvalidExecutionRequestError("result supports only image/tiff")
        return mode

    def _base_url(self):
        parsed = urlsplit(self.result_base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
        ):
            raise ProcessorExecuteError(user_msg="public result URL is not configured correctly")
        return self.result_base_url.rstrip("/")

    def format_result(self, value, response):
        headers = {"Cache-Control": "no-store"}
        if value.transmission == "reference":
            url = f"{self._base_url()}/results/{value.result.identifier}/output.tif"
            if response == "document":
                return ProcessResponse(
                    {"result": {"href": url, "type": TIFF_TYPE}}, "application/json", headers=headers
                )
            headers["Link"] = f'<{url}>; rel="item"; type="{TIFF_TYPE}"; title="result"'
            return ProcessResponse(b"", TIFF_TYPE, status=204, headers=headers)
        data, _ = value.store.read(value.result.identifier)
        if response == "document":
            document = {
                "result": {
                    "value": base64.b64encode(data).decode("ascii"),
                    "mediaType": TIFF_TYPE,
                    "encoding": "base64",
                }
            }
            return ProcessResponse(document, "application/json", headers=headers)
        headers["Content-Disposition"] = 'attachment; filename="output.tif"'
        return ProcessResponse(data, TIFF_TYPE, headers=headers)

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
                    "description": "Another warp is running or bounded result storage is full.",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
            },
        }
