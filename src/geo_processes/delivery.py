"""Represent a bounded stored output using the existing synchronous contract.

pygeoapi's processor interface returns a media type and value. Its stock
manager does not implement our expiring downloads or OGC results mapping;
this helper reuses the existing formatter hook without changing that lifecycle.
"""

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from pygeoapi.process.base import ProcessorExecuteError

from geo_processes.manager import InvalidExecutionRequestError
from geo_processes.responses import ProcessResponse
from geo_processes.storage import RESULT_TYPES, ResultStore, StoredResult


class ResultCapacityError(ProcessorExecuteError):
    """The bounded output store is busy or full."""

    http_status_code = 503
    ogc_exception_code = "ServerBusy"


@dataclass(frozen=True)
class FileOutput:
    result: StoredResult
    transmission: str
    store: ResultStore
    extension: str = "tif"
    output_id: str = "result"


def output_transmission(outputs, *, output_id="result", media_type="image/tiff"):
    if outputs is None:
        return "value"
    if not isinstance(outputs, Mapping) or set(outputs) != {output_id}:
        raise InvalidExecutionRequestError(f"outputs must select the defined {output_id} output")
    options = outputs[output_id]
    if not isinstance(options, Mapping) or set(options) - {"transmissionMode", "format"}:
        raise InvalidExecutionRequestError("unsupported output options")
    mode = options.get("transmissionMode", "value")
    if not isinstance(mode, str) or mode not in {"value", "reference"}:
        raise InvalidExecutionRequestError("transmissionMode must be value or reference")
    output_format = options.get("format", {})
    if not isinstance(output_format, Mapping) or set(output_format) - {"mediaType"}:
        raise InvalidExecutionRequestError("unsupported output format")
    if output_format.get("mediaType", media_type) != media_type:
        raise InvalidExecutionRequestError(f"output supports only {media_type}")
    return mode


def result_base_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
    ):
        raise ProcessorExecuteError(user_msg="public result URL is not configured correctly")
    return url.rstrip("/")


def format_file(value, response, base_url):
    media_type = RESULT_TYPES[value.extension]
    headers = {"Cache-Control": "no-store"}
    if value.transmission == "reference":
        url = f"{result_base_url(base_url)}/results/{value.result.identifier}/output.{value.extension}"
        if response == "document":
            return ProcessResponse(
                {value.output_id: {"href": url, "type": media_type}}, "application/json", headers=headers
            )
        headers["Link"] = f'<{url}>; rel="item"; type="{media_type}"; title="{value.output_id}"'
        return ProcessResponse(b"", media_type, status=204, headers=headers)
    data, _ = value.store.read(value.result.identifier, extension=value.extension)
    if response == "document":
        inline = (
            {"value": json.loads(data), "mediaType": media_type}
            if value.extension == "geojson"
            else {"value": base64.b64encode(data).decode("ascii"), "mediaType": media_type, "encoding": "base64"}
        )
        return ProcessResponse({value.output_id: inline}, "application/json", headers=headers)
    headers["Content-Disposition"] = f'attachment; filename="output.{value.extension}"'
    return ProcessResponse(data, media_type, headers=headers)
