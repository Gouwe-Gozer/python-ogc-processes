"""Flask boundary guard for registered synchronous process endpoints."""

from collections.abc import Mapping
from email.utils import formatdate
from itertools import chain

from flask import Blueprint, jsonify, make_response, request
from pygeoapi.flask_app import API_RULES, APP, CONFIG, api_, execute_from_flask
from werkzeug.datastructures import Headers

from geo_processes.datasets import SAMPLE_DATA_DIR
from geo_processes.discovery import landing_links, list_processes
from geo_processes.documentation import configure_documentation_templates
from geo_processes.errors import exception_document, install_exception_renderer
from geo_processes.inputs import MAX_EXECUTION_BYTES
from geo_processes.logging_filters import install_metadata_locale_filter
from geo_processes.responses import STATUS_HEADER
from geo_processes.startup import validate_runtime
from geo_processes.storage import RESULT_TYPES, ResultNotFoundError, ResultStore, ResultStoreError

runtime_settings = validate_runtime(CONFIG)
install_metadata_locale_filter(
    chain(
        (api_.manager.get_processor(identifier).metadata for identifier in api_.manager.processes),
        CONFIG["resources"].values(),
    ),
    literal_data=(
        definition
        for resource in CONFIG["resources"].values()
        for definition in ([resource["processor"]] if resource["type"] == "process" else resource.get("providers", []))
    ),
)
configure_documentation_templates(api_)
api_.manager.result_base_url = runtime_settings.url
install_exception_renderer(api_)
APP.config["MAX_CONTENT_LENGTH"] = MAX_EXECUTION_BYTES
APP.register_blueprint(
    Blueprint("sample_data", __name__, static_folder=str(SAMPLE_DATA_DIR), static_url_path="/sample-data"),
    url_prefix=(API_RULES.get_url_prefix("flask") or "").rstrip("/"),
)

EXECUTION_PATHS = {
    f"/processes/{identifier}/execution"
    for identifier, resource in CONFIG["resources"].items()
    if resource["type"] == "process"
}
ALLOWED_EXECUTION_MEMBERS = {"inputs", "outputs", "response"}

_upstream_get_processes = APP.view_functions["pygeoapi.get_processes"]


def get_processes(process_id=None):
    if process_id is not None:
        return _upstream_get_processes(process_id)
    return execute_from_flask(list_processes, request)


APP.view_functions["pygeoapi.get_processes"] = get_processes


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
    # Upstream assigns a plain dict; restore case-insensitive media-type lookups.
    response.headers = Headers(response.headers)
    # The pinned feature handler uses the generic JSON media type even though
    # its item(s) payload is GeoJSON. Keep discovery and error JSON unchanged.
    if (
        request.endpoint == "pygeoapi.collection_items"
        and response.status_code == 200
        and response.mimetype == "application/json"
    ):
        response.mimetype = "application/geo+json"
    status = response.headers.pop(STATUS_HEADER, None)
    if status == "204" and response.status_code == 200:
        response.status_code = 204
        response.set_data(b"")
        response.headers.pop("Content-Type", None)
    if request.endpoint == "pygeoapi.landing_page" and response.status_code == 200:
        return landing_links(response, api_)
    return response


@APP.route(f"{(API_RULES.get_url_prefix('flask') or '').rstrip('/')}/results/<result_id>/output.<extension>")
def download_result(result_id, extension):
    """Deliver only supported stored formats, enforcing lifetime on every read."""
    try:
        data, expires_at = ResultStore.from_environment().read(result_id, extension=extension)
    except ResultNotFoundError:
        return jsonify(exception_document("NoSuchResult", "result not found or expired", 404)), 404
    except (ResultStoreError, OSError):
        APP.logger.exception("Result storage read failed")
        return jsonify(exception_document("NoApplicableCode", "result could not be read", 500)), 500
    response = make_response(data)
    response.headers.update(
        {
            "Content-Type": RESULT_TYPES[extension],
            "Content-Disposition": f'attachment; filename="output.{extension}"',
            "Cache-Control": "no-store",
            "Expires": formatdate(expires_at, usegmt=True),
            "X-Content-Type-Options": "nosniff",
        }
    )
    return response
