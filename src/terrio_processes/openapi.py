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

from terrio_processes import __version__

SCHEMA_BASE = "https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi/schemas"


def schema_response(description, schema):
    return {
        "description": description,
        "content": {"application/json": {"schema": {"$ref": f"{SCHEMA_BASE}/{schema}"}}},
    }


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
    limits = config["server"].get("limits", {})
    listing.setdefault("parameters", []).append(
        {
            "name": "limit",
            "in": "query",
            "schema": {
                "type": "integer",
                "minimum": 1,
                "default": limits.get("default_items", 10),
                "maximum": limits.get("max_items", 50),
            },
        }
    )
    for identifier, resource in config["resources"].items():
        if resource["type"] != "process":
            continue
        path = f"/processes/{identifier}"
        paths[path]["get"]["responses"]["200"] = schema_response("Process description", "process.yaml")
        paths[path]["get"]["responses"]["404"] = schema_response("Unknown process", "exception.yaml")
        processor = load_plugin("process", resource["processor"])
        contract = getattr(processor, "openapi_execution", None)
        if contract is None:
            continue
        execution = paths[f"{path}/execution"]["post"]
        override = contract()
        execution["requestBody"] = override["requestBody"]
        execution["responses"].update(override["responses"])
        execution["responses"]["400"] = schema_response("Invalid execution request", "exception.yaml")
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
