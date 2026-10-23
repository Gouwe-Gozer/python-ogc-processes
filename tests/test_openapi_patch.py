"""Compare upstream 0.24.0 output with the actual public HTTP contract."""

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from pygeoapi.openapi import get_oas, validate_openapi_document
from pygeoapi.process.manager.dummy import DummyManager

from geo_processes.contracts.info import DATASETS
from geo_processes.openapi import SCHEMA_BASE, generate_openapi


def test_upstream_still_needs_targeted_corrections(service_config):
    upstream = get_oas(deepcopy(service_config))
    paths = upstream["paths"]
    assert not any(path.startswith("/jobs") for path in paths)
    execution = paths["/processes/raster-info/execution"]["post"]
    assert "201" in execution["responses"]
    assert paths["/conformance"]["get"]["responses"]["200"]["$ref"].endswith("/LandingPage")
    assert not any(p.get("name") == "limit" for p in paths["/processes"]["get"]["parameters"])
    manager = DummyManager({"name": "Dummy", "processes": service_config["resources"]})
    document = manager.execute_process("raster-info", {"source": "demo-dem"}, requested_response="document")[2]
    assert set(document) == {"outputs"}
    assert document["outputs"][0]["type"] == "raster"


def test_generated_openapi_is_valid_and_preserves_description(service_config):
    document = generate_openapi(service_config)
    assert validate_openapi_document(document)
    assert document["info"]["title"] == "Geo Processes API"
    assert not any(path.startswith("/jobs") for path in document["paths"])
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
        payload = {"inputs": {"source": "demo-dem"}, "response": mode}
        Draft202012Validator(request_schema).validate(payload)
        result = http_client.post("/processes/raster-info/execution", json=payload)
        Draft202012Validator(result_schema).validate(result.get_json())
    assert DATASETS["demo-dem"].is_file()


def test_corrections_are_version_aware(service_config, monkeypatch):
    monkeypatch.setattr("geo_processes.openapi.version", lambda _: "future")
    with pytest.raises(RuntimeError, match="reassess"):
        generate_openapi(service_config)
