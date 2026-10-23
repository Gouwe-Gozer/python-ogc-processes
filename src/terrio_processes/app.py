"""Flask boundary guard for registered synchronous process endpoints."""

from collections.abc import Mapping

from flask import jsonify, request
from pygeoapi.flask_app import APP, CONFIG

EXECUTION_PATHS = {
    f"/processes/{identifier}/execution"
    for identifier, resource in CONFIG["resources"].items()
    if resource["type"] == "process"
}
ALLOWED_EXECUTION_MEMBERS = {"inputs", "outputs", "response"}


def _invalid_request(description):
    return jsonify(type="InvalidParameterValue", code="InvalidParameterValue", description=description), 400


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
