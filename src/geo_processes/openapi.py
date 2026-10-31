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
from geo_processes.discovery import readonly_geojson_collections
from geo_processes.errors import exception_document

SCHEMA_BASE = "https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi/schemas"
HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})


def _remove_unused_tags(document):
    """Keep declared tag metadata only when an operation uses that grouping."""
    used_tags = {
        tag
        for path in document["paths"].values()
        for method, operation in path.items()
        if method in HTTP_METHODS
        for tag in operation.get("tags", [])
    }
    document["tags"] = [tag for tag in document.get("tags", []) if tag["name"] in used_tags]


def schema_response(description, schema):
    return {
        "description": description,
        "content": {"application/json": {"schema": {"$ref": f"{SCHEMA_BASE}/{schema}"}}},
    }


def job_status_response(description):
    response = schema_response(description, "statusInfo.yaml")
    schema = response["content"]["application/json"]["schema"]
    response["content"]["application/json"]["schema"] = {
        "allOf": [schema, {"type": "object", "required": ["processID"]}]
    }
    return response


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
    durable_async = (
        config["server"].get("manager", {}).get("name") == "geo_processes.async_manager.DurableProcessManager"
    )
    document["info"]["version"] = __version__
    document["info"].pop("contact", None)
    paths = document["paths"]
    if durable_async:
        paths.get("/jobs/{jobId}", {}).pop("delete", None)
    for identifier in readonly_geojson_collections(config):
        # In the pinned generator this POST is a CQL query, not feature creation.
        # GeoJSONProvider accepts but ignores filterq, so it is unsupported here.
        paths.get(f"/collections/{identifier}/items", {}).pop("post", None)
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
    if durable_async:
        response = schema_response("Retained job statuses", "jobList.yaml")
        schema = response["content"]["application/json"]["schema"]
        response["content"]["application/json"]["schema"] = {
            "allOf": [
                schema,
                {
                    "type": "object",
                    "properties": {"jobs": {"type": "array", "items": {"type": "object", "required": ["processID"]}}},
                },
            ]
        }
        response["content"]["text/html"] = {"schema": {"type": "string"}}
        parameters = [
            {
                "name": name,
                "in": "query",
                "required": False,
                "style": "form",
                "explode": name != "maxDuration",
                "description": description,
                "schema": {"type": "array", "items": {"type": kind}},
            }
            for name, kind, description in (
                ("type", "string", "Job types; only process jobs are stored"),
                ("processID", "string", "Process identifiers (OR within this filter)"),
                ("status", "string", "Job statuses (OR within this filter)"),
                ("minDuration", "integer", "Minimum execution seconds; all supplied bounds apply"),
                ("maxDuration", "integer", "Maximum execution seconds; all supplied bounds apply"),
            )
        ]
        parameters += [
            {
                "name": "datetime",
                "in": "query",
                "description": "Created time: RFC 3339 instant or inclusive interval; .. denotes an open end",
                "schema": {"type": "string"},
            },
            {"name": "f", "in": "query", "schema": {"type": "string", "enum": ["json", "html"]}},
            *deepcopy(listing["parameters"][-2:]),
        ]
        paths["/jobs"] = {
            "get": {
                "summary": "List retained asynchronous jobs",
                "description": (
                    "Filters combine with AND. Pagination uses offset in stable creation order. "
                    "Only retained async jobs are listed; this deployment has no per-user ownership filtering."
                ),
                "operationId": "getJobs",
                "tags": ["jobs"],
                "parameters": parameters,
                "responses": {
                    "200": response,
                    "400": exception_response("Invalid job-list query", "InvalidParameterValue", 400),
                    "503": exception_response("Job database unavailable", "ServerBusy", 503),
                },
            }
        }
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
        if durable_async:
            operation["responses"]["200"] = (
                job_status_response("Job status")
                if not suffix
                else {
                    "description": "Stored response in the originally requested format and transmission mode",
                    "content": {
                        "application/json": {"schema": {}},
                        "image/tiff": {"schema": {"type": "string", "format": "binary"}},
                        "application/geo+json": {"schema": {"type": "object"}},
                    },
                }
            )
            operation["responses"]["503"] = exception_response("Job database unavailable", "ServerBusy", 503)
            if suffix:
                operation["responses"]["204"] = {"description": "Raw/reference result; download URL in Link header"}
                operation["responses"]["500"] = exception_response(
                    "Execution failed or interrupted", "NoApplicableCode", 500
                )
                operation["responses"]["413"] = exception_response("Input too large", "RequestTooLarge", 413)
                operation["responses"]["404"]["description"] = "Unknown/expired job, or ResultNotReady while pending"
    for identifier, resource in config["resources"].items():
        if resource["type"] == "collection":
            operation = paths.get(f"/collections/{identifier}/items", {}).get("get", {})
            # Upstream emits enum: [] for property selection on features with
            # empty properties. There are no selectable properties to advertise.
            if "parameters" in operation:
                operation["parameters"] = [
                    parameter
                    for parameter in operation["parameters"]
                    if not (
                        parameter.get("name") == "properties"
                        and parameter.get("schema", {}).get("items", {}).get("enum") == []
                    )
                ]
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
            "Request body or process input exceeds its supported size limit", "RequestTooLarge", 413
        )
        execution["responses"]["500"] = exception_response("Process execution failed", "NoApplicableCode", 500)
        execution["responses"]["503"] = exception_response("Processing capacity unavailable", "ServerBusy", 503)
        if durable_async:
            execution["responses"]["201"] = job_status_response("Job accepted for independent execution")
            execution["responses"]["201"]["headers"] = {
                "Location": {"schema": {"type": "string", "format": "uri"}, "description": "Job status URL"},
                "Preference-Applied": {"schema": {"type": "string", "enum": ["respond-async"]}},
            }
            execution["parameters"] = [
                {
                    "name": "Prefer",
                    "in": "header",
                    "description": "Default is synchronous; respond-async queues a durable job",
                    "schema": {"type": "string", "enum": ["wait", "respond-async"]},
                }
            ]
        elif processor.metadata["jobControlOptions"] == ["sync-execute"]:
            execution["responses"].pop("201", None)
            execution["parameters"] = [
                {
                    "name": "Prefer",
                    "in": "header",
                    "description": "Execution stays synchronous; respond-async is ignored.",
                    "schema": {"type": "string", "enum": ["wait", "respond-async"]},
                }
            ]
    from geo_processes.storage import RESULT_TYPES

    for extension, media_type in RESULT_TYPES.items():
        tags = [
            identifier
            for identifier, resource in config["resources"].items()
            if resource["type"] == "process"
            and getattr(load_plugin("process", resource["processor"]), "result_extension", None) == extension
        ]
        if not tags:
            continue
        # This is application storage delivery, separate from OGC job management.
        paths[f"/results/{{result_id}}/output.{extension}"] = {
            "get": {
                "summary": "Download an unexpired processing result",
                "operationId": f"downloadResult{extension.title()}",
                "tags": tags,
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
                        "description": "Stored result, available until the Expires time (24 hours by default)",
                        "content": {
                            media_type: {
                                "schema": {"type": "object"}
                                if extension == "geojson"
                                else {"type": "string", "format": "binary"}
                            }
                        },
                        "headers": {"Expires": {"schema": {"type": "string"}, "description": "Result expiration time"}},
                    },
                    "404": exception_response("Result missing, invalid or expired", "NoSuchResult", 404, html=False),
                    "500": exception_response("Result could not be read", "NoApplicableCode", 500, html=False),
                },
            }
        }
    if "sample-points" in config["resources"]:
        paths["/sample-data/AHN4_R5_117000_517000.TIF"] = {
            "get": {
                "summary": "Download the matching AHN4 sample GeoTIFF",
                "operationId": "downloadSampleRaster",
                "responses": {
                    "200": {
                        "description": "Packaged, unchanged AHN4 sample raster.",
                        "content": {"image/tiff": {"schema": {"type": "string", "format": "binary"}}},
                    }
                },
            }
        }
    _remove_unused_tags(document)
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
