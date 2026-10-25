"""Compare upstream 0.24.0 output with the actual public HTTP contract."""

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from pygeoapi.openapi import get_oas, validate_openapi_document
from pygeoapi.process.manager.dummy import DummyManager
from raster_fixtures import DEMO_SOURCE

from geo_processes.datasets import DEMO_RASTER
from geo_processes.openapi import SCHEMA_BASE, _remove_unused_tags, generate_openapi


def test_tag_cleanup_preserves_operations_groupings_and_used_tag_metadata():
    methods = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
    used = [{"name": method, "description": f"Group for {method}"} for method in reversed(methods)]
    used[0]["externalDocs"] = {"url": "https://example.test/documentation"}
    document = {
        "tags": [{"name": "unused"}, *used, {"name": "path-metadata"}],
        "paths": {
            "/example": {
                "summary": "An example path",
                "parameters": [],
                "x-metadata": {"tags": ["path-metadata"]},
                **{method: {"tags": [method, "implicit-group"], "responses": {}} for method in methods},
            },
            "/untagged": {"get": {"responses": {}}},
        },
        "info": {"title": "Unchanged"},
    }
    expected = deepcopy(document)
    expected["tags"] = deepcopy(used)
    _remove_unused_tags(document)
    assert document == expected


def test_generated_openapi_omits_only_unused_tag_declarations(service_config):
    upstream = get_oas(deepcopy(service_config))
    document = generate_openapi(service_config)
    tags = {tag["name"] for tag in document["tags"]}
    assert tags == {"server", "sample-points", "sample-polygons"}
    assert {tag["name"] for tag in upstream["tags"]} - tags == {
        "coverages",
        "edr",
        "records",
        "features",
        "maps",
        "processes",
        "tiles",
        "stac",
    }
    for path, item in upstream["paths"].items():
        for method, operation in item.items():
            if method in {"get", "post", "delete"}:
                assert document["paths"][path][method].get("tags") == operation.get("tags")


def test_upstream_still_needs_targeted_corrections(service_config):
    upstream = get_oas(deepcopy(service_config))
    paths = upstream["paths"]
    assert not any(path.startswith("/jobs") for path in paths)
    execution = paths["/processes/raster-info/execution"]["post"]
    assert "201" in execution["responses"]
    assert paths["/conformance"]["get"]["responses"]["200"]["$ref"].endswith("/LandingPage")
    assert not any(p.get("name") == "limit" for p in paths["/processes"]["get"]["parameters"])
    manager = DummyManager({"name": "Dummy", "processes": service_config["resources"]})
    document = manager.execute_process("raster-info", {"source": DEMO_SOURCE}, requested_response="document")[2]
    assert set(document) == {"outputs"}
    assert document["outputs"][0]["type"] == "raster"


def test_generated_openapi_is_valid_and_preserves_description(service_config):
    document = generate_openapi(service_config)
    assert validate_openapi_document(document)
    assert document["info"]["title"] == "Raster Processes API"
    assert document["info"]["description"] == service_config["metadata"]["identification"]["description"]
    assert document["info"]["description"].startswith(
        "An OGC API – Processes service for raster operations, powered by pygeoapi and rasterio/GDAL."
    )
    assert "OGC API – Processes Part 1: Core" in document["info"]["description"]
    assert "synchronous execution, with asynchronous job management planned" in document["info"]["description"]
    assert {"/jobs/{jobID}", "/jobs/{jobID}/results"} <= document["paths"].keys()
    assert "/jobs" not in document["paths"]
    assert "bgt-land-cover-summary" not in str(document)


def test_runtime_openapi_describes_real_responses(http_client):
    response = http_client.get("/openapi?f=json")
    assert response.status_code == 200
    document = response.get_json()
    paths = document["paths"]
    assert paths["/conformance"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": f"{SCHEMA_BASE}/confClasses.yaml"
    }
    assert paths["/processes"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": f"{SCHEMA_BASE}/processList.yaml"
    }
    assert "404" in paths["/processes/raster-info"]["get"]["responses"]
    operation = paths["/processes/raster-info/execution"]["post"]
    assert "201" not in operation["responses"]
    assert "400" in operation["responses"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    result_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    for mode in ["raw", "document"]:
        payload = {"inputs": {"source": DEMO_SOURCE}, "response": mode}
        Draft202012Validator(request_schema).validate(payload)
        result = http_client.post("/processes/raster-info/execution", json=payload)
        Draft202012Validator(result_schema).validate(result.get_json())
    assert DEMO_RASTER.is_file()


def test_corrections_are_version_aware(service_config, monkeypatch):
    monkeypatch.setattr("geo_processes.openapi.version", lambda _: "future")
    with pytest.raises(RuntimeError, match="reassess"):
        generate_openapi(service_config)


def test_job_documentation_preserves_the_existing_async_manager_contract():
    from pathlib import Path

    import yaml

    config = yaml.safe_load(Path("config/pygeoapi.integration.yml").read_text())
    config["server"]["url"] = "http://example.test"
    document = generate_openapi(config)
    assert validate_openapi_document(document)
    paths = document["paths"]
    assert "/jobs" in paths
    for suffix in ("", "/results"):
        responses = paths[f"/jobs/{{jobId}}{suffix}"]["get"]["responses"]
        assert "200" in responses and "404" in responses
        assert responses["404"]["content"]["application/json"]["example"]["type"].endswith("/no-such-job")
