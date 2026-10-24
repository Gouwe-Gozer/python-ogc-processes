"""Flask boundary guard for registered synchronous process endpoints."""

from collections.abc import Mapping
from email.utils import formatdate

from flask import jsonify, make_response, request
from pygeoapi.flask_app import API_RULES, APP, CONFIG, api_
from werkzeug.datastructures import Headers

from geo_processes.errors import EXCEPTIONS, exception_document
from geo_processes.inputs import MAX_EXECUTION_BYTES
from geo_processes.responses import STATUS_HEADER
from geo_processes.startup import validate_runtime
from geo_processes.storage import ResultNotFoundError, ResultStore, ResultStoreError

runtime_settings = validate_runtime(CONFIG)
api_.manager.result_base_url = runtime_settings.url
APP.config["MAX_CONTENT_LENGTH"] = MAX_EXECUTION_BYTES

EXECUTION_PATHS = {
    f"/processes/{identifier}/execution"
    for identifier, resource in CONFIG["resources"].items()
    if resource["type"] == "process"
}
ALLOWED_EXECUTION_MEMBERS = {"inputs", "outputs", "response"}


def _invalid_request(description):
    return jsonify(exception_document("InvalidParameterValue", description, 400)), 400


@APP.errorhandler(413)
def execution_document_too_large(_error):
    return jsonify(exception_document("RequestTooLarge", "request body exceeds 24 MiB", 413)), 413


@APP.before_request
def validate_execution_document():
    """Guard shapes pygeoapi 0.24.0 dereferences without type validation."""
    # url_rule handles trailing slashes and configured URL prefixes.
    if request.method != "POST" or request.url_rule is None or request.view_args is None:
        return None
    identifier = request.view_args.get("process_id")
    if f"/processes/{identifier}/execution" not in EXECUTION_PATHS or not request.path.rstrip("/").endswith(
        "/execution"
    ):
        return None
    document = request.get_json(silent=True)
    if not isinstance(document, Mapping):
        return _invalid_request("execution request must be a JSON object")
    if set(document) - ALLOWED_EXECUTION_MEMBERS:
        return _invalid_request("unsupported execution member; subscriber callbacks are not supported")
    if not isinstance(document.get("inputs"), Mapping):
        return _invalid_request("inputs must be an object")
    if "outputs" in document and not isinstance(document["outputs"], Mapping):
        return _invalid_request("outputs must be an object")
    if "response" in document and (
        not isinstance(document["response"], str) or document["response"] not in {"raw", "document"}
    ):
        return _invalid_request("response must be either raw or document")
    return None


@APP.after_request
def apply_process_status(response):
    """pygeoapi 0.24.0 fixes successful executions at 200; honor explicit 204s."""
    status = response.headers.pop(STATUS_HEADER, None)
    if status == "204" and response.status_code == 200:
        response.status_code = 204
        response.set_data(b"")
        response.headers.pop("Content-Type", None)
    return response


@APP.after_request
def apply_exception_catalogue(response):
    """Normalize known pygeoapi JSON exceptions without changing HTTP status."""
    if response.status_code >= 400:
        # Upstream assigns a plain dict to response.headers. Restore case-
        # insensitive lookups before Flask checks the response media type.
        response.headers = Headers(response.headers)
    if response.status_code >= 400 and response.is_json:
        document = response.get_json(silent=True)
        if (
            isinstance(document, dict)
            and isinstance(document.get("code"), str)
            and document["code"] in EXCEPTIONS
            and isinstance(document.get("description"), str)
        ):
            document.update(exception_document(document["code"], document["description"], response.status_code))
            response.set_data(APP.json.dumps(document))
    return response


@APP.route(f"{(API_RULES.get_url_prefix('flask') or '').rstrip('/')}/results/<result_id>/output.tif")
def download_result(result_id):
    """Deliver a generated GeoTIFF, enforcing its lifetime on every retrieval."""
    try:
        data, expires_at = ResultStore.from_environment().read(result_id)
    except ResultNotFoundError:
        return jsonify(exception_document("NoSuchResult", "result not found or expired", 404)), 404
    except (ResultStoreError, OSError):
        APP.logger.exception("Result storage read failed")
        return jsonify(exception_document("NoApplicableCode", "result could not be read", 500)), 500
    response = make_response(data)
    response.headers.update(
        {
            "Content-Type": "image/tiff",
            "Content-Disposition": 'attachment; filename="output.tif"',
            "Cache-Control": "no-store",
            "Expires": formatdate(expires_at, usegmt=True),
            "X-Content-Type-Options": "nosniff",
        }
    )
    return response
