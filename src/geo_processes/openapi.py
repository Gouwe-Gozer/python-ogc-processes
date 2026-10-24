"""Focused corrections to the pinned pygeoapi 0.24.0 OpenAPI generator.

Retain upstream paths and schemas wherever they match HTTP behavior. Each
processor supplies its own execution schema and result media types.
"""

import argparse
from copy import deepcopy
from importlib.metadata import version
from pathlib import Path

import yaml
from pygeoapi.openapi import get_oas
from pygeoapi.plugin import load_plugin
from pygeoapi.util import yaml_load

from geo_processes import __version__
from geo_processes.errors import exception_document

SCHEMA_BASE = "https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi/schemas"


def schema_response(description, schema):
    return {
        "description": description,
        "content": {"application/json": {"schema": {"$ref": f"{SCHEMA_BASE}/{schema}"}}},
    }


def exception_response(description, code, status, *, html=True):
    response = schema_response(description, "exception.yaml")
    response["content"]["application/json"]["example"] = exception_document(code, description, status)
    if html:
        response["content"]["text/html"] = {"schema": {"type": "string"}}
    return response


def generate_openapi(config):
    """Generate the actual public definition, failing closed on untested upgrades."""
    if version("pygeoapi") != "0.24.0":
        raise RuntimeError("reassess OpenAPI compatibility corrections for this pygeoapi version")
    document = get_oas(deepcopy(config))
    document["info"]["version"] = __version__
    document["info"].pop("contact", None)
    paths = document["paths"]
    paths["/conformance"]["get"]["responses"]["200"] = schema_response(
        "Supported conformance classes", "confClasses.yaml"
    )
    listing = paths["/processes"]["get"]
    listing["responses"]["200"] = schema_response("Available processes", "processList.yaml")
    listing["responses"]["400"] = exception_response("Invalid limit", "InvalidParameterValue", 400)
    limits = config["server"].get("limits", {})
    listing.setdefault("parameters", []).append(
        {
            "name": "limit",
            "in": "query",
            "required": False,
            "style": "form",
            "explode": False,
            "schema": {
                "type": "integer",
                "minimum": 1,
                "default": limits.get("default_items", 10),
                "maximum": limits.get("max_items", 50),
            },
        }
    )
    listing["parameters"].append(
        {"name": "offset", "in": "query", "schema": {"type": "integer", "minimum": 0, "default": 0}}
    )
    for suffix, title in (("", "Job status"), ("/results", "Job results")):
        # Preserve upstream's complete operations if a future async manager is
        # configured. The current manager stores no jobs: every ID is unknown.
        upstream_path = f"/jobs/{{jobId}}{suffix}"
        path = upstream_path if upstream_path in paths else f"/jobs/{{jobID}}{suffix}"
        parameter = "jobId" if path == upstream_path else "jobID"
        operation = paths.setdefault(path, {}).setdefault(
            "get",
            {
                "summary": title,
                "description": "The synchronous manager stores no jobs; every identifier returns 404.",
                "operationId": "getCoreJobStatus" if not suffix else "getCoreJobResults",
                "parameters": [{"name": parameter, "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {},
            },
        )
        operation["responses"]["404"] = exception_response("Unknown job identifier", "NoSuchJob", 404)
        operation["responses"]["400"] = exception_response("Invalid query parameter", "InvalidParameterValue", 400)
    for identifier, resource in config["resources"].items():
        if resource["type"] != "process":
            continue
        path = f"/processes/{identifier}"
        paths[path]["get"]["responses"]["200"] = schema_response("Process description", "process.yaml")
        paths[path]["get"]["responses"]["404"] = exception_response("Unknown process", "NoSuchProcess", 404)
        processor = load_plugin("process", resource["processor"])
        contract = getattr(processor, "openapi_execution", None)
        if contract is None:
            continue
        execution = paths[f"{path}/execution"]["post"]
        override = contract()
        execution["requestBody"] = override["requestBody"]
        execution["responses"].update(override["responses"])
        execution["responses"]["400"] = exception_response("Invalid execution request", "InvalidParameterValue", 400)
        execution["responses"]["404"] = exception_response("Unknown process", "NoSuchProcess", 404)
        execution["responses"]["413"] = exception_response(
            "Request body exceeds 24 MiB or raster exceeds 16 MiB", "RequestTooLarge", 413
        )
        execution["responses"]["500"] = exception_response("Process execution failed", "NoApplicableCode", 500)
        execution["responses"]["503"] = exception_response("Processing capacity unavailable", "ServerBusy", 503)
        if processor.metadata["jobControlOptions"] == ["sync-execute"]:
            execution["responses"].pop("201", None)
            execution["parameters"] = [
                {
                    "name": "Prefer",
                    "in": "header",
                    "description": "Execution stays synchronous; respond-async is ignored.",
                    "schema": {"type": "string", "enum": ["wait", "respond-async"]},
                }
            ]
    if "raster-warp" in config["resources"]:
        # This is application storage delivery, separate from OGC job management.
        paths["/results/{result_id}/output.tif"] = {
            "get": {
                "summary": "Download an unexpired raster result",
                "operationId": "downloadRasterResult",
                "tags": ["raster-warp"],
                "parameters": [
                    {
                        "name": "result_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "pattern": "^[0-9a-f]{32}$"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "GeoTIFF, available until the Expires time (24 hours by default)",
                        "content": {"image/tiff": {"schema": {"type": "string", "format": "binary"}}},
                        "headers": {"Expires": {"schema": {"type": "string"}, "description": "Result expiration time"}},
                    },
                    "404": exception_response("Result missing, invalid or expired", "NoSuchResult", 404, html=False),
                    "500": exception_response("Result could not be read", "NoApplicableCode", 500, html=False),
                },
            }
        }
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/pygeoapi.yml"))
    parser.add_argument("--output", type=Path, default=Path("pygeoapi-openapi.yml"))
    args = parser.parse_args()
    with args.config.open(encoding="utf-8") as config_file:
        config = yaml_load(config_file)
    args.output.write_text(yaml.safe_dump(generate_openapi(config), sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    main()
