"""Flask boundary guard for registered synchronous process endpoints."""

from collections.abc import Mapping
from email.utils import formatdate
from itertools import chain

from flask import Blueprint, jsonify, make_response, request
from pygeoapi.flask_app import API_RULES, APP, CONFIG, api_, execute_from_flask
from werkzeug.datastructures import Headers

from geo_processes.datasets import SAMPLE_DATA_DIR
from geo_processes.discovery import (
    conformance,
    describe_process,
    landing_links,
    landing_page,
    list_processes,
    readonly_geojson_collections,
)
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
# Reuse pygeoapi's canonical URL, including any native api_rules route prefix.
api_.manager.result_base_url = api_.base_url
install_exception_renderer(api_)
APP.config["MAX_CONTENT_LENGTH"] = MAX_EXECUTION_BYTES
APP.register_blueprint(
    Blueprint("assets", __name__, static_folder="static", static_url_path="/assets"),
    url_prefix=(API_RULES.get_url_prefix("flask") or "").rstrip("/"),
)
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


@APP.before_request
def durable_job_routes():
    if not getattr(api_.manager, "durable_async", False):
        return None
    if request.endpoint not in {"pygeoapi.get_jobs", "pygeoapi.get_job_result"}:
        return None
    identifier = (request.view_args or {}).get("job_id")
    allowed = "GET, HEAD, OPTIONS" if identifier is not None else "OPTIONS"
    if request.method == "OPTIONS":
        return "", 204, {"Allow": allowed}
    if identifier is None or request.method not in {"GET", "HEAD"}:
        return (
            jsonify(exception_document("NoApplicableCode", "job listing and dismissal are not supported", 405)),
            405,
            {"Allow": allowed},
        )
    from geo_processes.jobs import job_response

    return job_response(api_, identifier, results=request.endpoint == "pygeoapi.get_job_result")


_upstream_get_processes = APP.view_functions["pygeoapi.get_processes"]


def get_processes(process_id=None):
    if process_id is not None:
        if getattr(api_.manager, "durable_async", False):
            return execute_from_flask(describe_process, request, process_id)
        return _upstream_get_processes(process_id)
    return execute_from_flask(list_processes, request)


APP.view_functions["pygeoapi.get_processes"] = get_processes


def get_conformance():
    return execute_from_flask(conformance, request)


APP.view_functions["pygeoapi.conformance"] = get_conformance


def get_landing_page():
    return execute_from_flask(landing_page, request)


APP.view_functions["pygeoapi.landing_page"] = get_landing_page


def _invalid_request(description):
    return jsonify(exception_document("InvalidParameterValue", description, 400)), 400


@APP.before_request
def reject_unsupported_sample_filtering():
    """GeoJSONProvider ignores filterq; never silently return unfiltered data."""
    arguments = request.view_args or {}
    if (
        request.endpoint != "pygeoapi.collection_items"
        or arguments.get("item_id") is not None
        or arguments.get("collection_id") not in readonly_geojson_collections(CONFIG)
    ):
        return None
    if (request.method == "POST" and request.mimetype != "application/geo+json") or set(request.args) & {
        "filter",
        "filter-lang",
        "filter-crs",
    }:
        return _invalid_request("CQL filtering is not supported for this sample collection; use bbox or feature IDs")
    return None


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
    # Job state and errors are dynamic, including early returns from route guards.
    if getattr(api_.manager, "durable_async", False) and request.endpoint in {
        "pygeoapi.get_jobs",
        "pygeoapi.get_job_result",
    }:
        response.headers["Cache-Control"] = "no-store"
    if (
        getattr(api_.manager, "durable_async", False)
        and request.path.rstrip("/").endswith("/execution")
        and response.status_code != 201
    ):
        response.headers.pop("Location", None)
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
