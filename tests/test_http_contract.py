"""HTTP contract tests through real Flask routes, manager, processor and Rasterio."""

import json
import urllib.request
from urllib.parse import urlsplit

import pytest
from jsonschema import Draft202012Validator

from geo_processes import engine
from geo_processes.contracts.info import DOCUMENT_SCHEMA, EXECUTE_SCHEMA, INFO_SCHEMA

EXECUTION_PATH = "/processes/raster-info/execution"
VALID_INPUTS = {"source": "demo-dem"}


@pytest.mark.parametrize("response_mode", [None, "raw", "document"])
@pytest.mark.parametrize(
    "outputs", [None, {"info": {}}, {"info": {"transmissionMode": "value"}}, {"info": {"format": {}}}]
)
def test_execution_defaults_and_explicit_options(http_client, response_mode, outputs):
    request = {"inputs": VALID_INPUTS}
    if response_mode is not None:
        request["response"] = response_mode
    if outputs is not None:
        request["outputs"] = outputs
    Draft202012Validator(EXECUTE_SCHEMA).validate(request)
    response = http_client.post(EXECUTION_PATH, json=request)
    assert response.status_code == 200
    assert response.content_type == "application/json"
    result = response.get_json()
    schema = DOCUMENT_SCHEMA if response_mode == "document" else INFO_SCHEMA
    Draft202012Validator(schema).validate(result)
    info = result["info"]["value"] if response_mode == "document" else result
    assert info["size"] == [4, 3]
    assert info["crs"]["epsg"] == 28992
    assert info["bands"][0]["statistics"]["mean"] == 6.5
    assert "Location" not in response.headers


@pytest.mark.parametrize(
    "document",
    [
        [],
        None,
        True,
        "raster",
        123,
        {},
        {"inputs": None},
        {"inputs": []},
        {"inputs": {"source": 1}},
        {"inputs": {"source": True}},
        {"inputs": {"source": {"href": "https://example.test/dem.tif"}}},
        {"inputs": {"source": ["demo-dem"]}},
        {"inputs": {"source": "/etc/passwd"}},
        {"inputs": {"source": "../../demo-dem"}},
        {"inputs": {"source": "https://example.test/dem.tif"}},
        {"inputs": {"source": "file:///etc/passwd"}},
        {"inputs": {"source": "missing"}},
        {"inputs": {**VALID_INPUTS, "extra": 1}},
        {"inputs": VALID_INPUTS, "response": []},
        {"inputs": VALID_INPUTS, "response": "unsupported"},
        {"inputs": VALID_INPUTS, "outputs": None},
        {"inputs": VALID_INPUTS, "outputs": []},
        {"inputs": VALID_INPUTS, "outputs": {}},
        {"inputs": VALID_INPUTS, "outputs": {"unknown": {}}},
        {"inputs": VALID_INPUTS, "outputs": {"info": None}},
        {"inputs": VALID_INPUTS, "outputs": {"info": {"extra": 1}}},
        {"inputs": VALID_INPUTS, "outputs": {"info": {"transmissionMode": "reference"}}},
        {"inputs": VALID_INPUTS, "outputs": {"info": {"format": None}}},
        {"inputs": VALID_INPUTS, "outputs": {"info": {"format": {"mediaType": "image/tiff"}}}},
        {"inputs": VALID_INPUTS, "outputs": {"info": {"format": {"encoding": "base64"}}}},
        {"inputs": VALID_INPUTS, "outputs": {"info": {"format": {"schema": "https://example.test/schema"}}}},
        {"inputs": VALID_INPUTS, "subscriber": {}},
        {"inputs": VALID_INPUTS, "subscriber": "callback"},
        {"inputs": VALID_INPUTS, "subscriber": {"successUri": "https://example.test/callback"}},
        {"inputs": VALID_INPUTS, "mode": "async"},
        {"inputs": VALID_INPUTS, "unexpected": True},
    ],
)
def test_malformed_or_unsupported_requests_are_controlled_errors(http_client, monkeypatch, document):
    def must_not_execute(*args, **kwargs):
        pytest.fail("Rasterio must not run for an invalid execution request")

    monkeypatch.setattr(engine, "raster_info", must_not_execute)
    assert not Draft202012Validator(EXECUTE_SCHEMA).is_valid(document)
    response = http_client.post(EXECUTION_PATH, data=json.dumps(document), content_type="application/json")
    assert response.status_code == 400
    assert response.content_type == "application/json"
    exception = response.get_json()
    assert exception["type"] == "InvalidParameterValue"
    assert exception["description"]
    assert "/home/" not in response.text
    assert "Traceback" not in response.text


@pytest.mark.parametrize("data", ["{", "", "not json"])
def test_invalid_json_is_a_client_error(http_client, data):
    response = http_client.post(EXECUTION_PATH, data=data, content_type="application/json")
    assert response.status_code == 400
    assert response.is_json


def test_engine_failure_is_a_sanitized_server_error(http_client, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("/private/server/path/secret.tif")

    monkeypatch.setattr(engine.rasterio, "open", fail)
    response = http_client.post(EXECUTION_PATH, json={"inputs": VALID_INPUTS})
    assert response.status_code == 500
    assert response.is_json
    assert "secret" not in response.text
    assert response.get_json()["description"] == "configured raster could not be inspected"


@pytest.mark.parametrize("preference", ["respond-async", "wait"])
def test_preferences_remain_synchronous(http_client, preference):
    response = http_client.post(EXECUTION_PATH, json={"inputs": VALID_INPUTS}, headers={"Prefer": preference})
    assert response.status_code == 200
    assert response.get_json()["type"] == "raster"
    assert "Location" not in response.headers
    assert response.headers.get("Preference-Applied") == ("wait" if preference == "wait" else None)


def test_discovery_links_descriptions_and_capabilities_agree(http_client):
    landing = http_client.get("/?f=json")
    assert landing.status_code == 200
    assert landing.get_json()["title"] == "Geo Processes API"
    listing = http_client.get("/processes?f=json").get_json()
    assert {process["id"] for process in listing["processes"]} == {"raster-info", "raster-warp"}
    process = next(process for process in listing["processes"] if process["id"] == "raster-info")
    description_link = next(link for link in process["links"] if link["type"] == "application/json")
    parsed = urlsplit(description_link["href"])
    response = http_client.get(f"{parsed.path}?{parsed.query}")
    assert response.status_code == 200
    description = response.get_json()
    assert description["id"] == process["id"]
    assert description["jobControlOptions"] == ["sync-execute"]
    assert description["outputTransmission"] == ["value"]
    assert description["inputs"]["source"]["schema"] == {"type": "string", "enum": ["demo-dem"]}
    assert description["outputs"]["info"]["schema"]["contentMediaType"] == "application/json"
    execution = next(link for link in description["links"] if link["rel"].endswith("/execute"))
    assert urlsplit(execution["href"]).path == EXECUTION_PATH
    for link in landing.get_json()["links"]:
        assert not link["rel"].endswith("/job-list")


def test_conformance_excludes_unimplemented_optional_classes(http_client):
    classes = http_client.get("/conformance?f=json").get_json()["conformsTo"]
    base = "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/"
    assert {base + name for name in ["core", "json", "oas30", "ogc-process-description"]} <= set(classes)
    assert not {base + name for name in ["callback", "job-list", "dismiss"]} & set(classes)


@pytest.mark.parametrize("path", ["/processes/unknown", "/processes/bgt-land-cover-summary"])
def test_retired_and_unknown_processes_are_not_available(http_client, path):
    assert http_client.get(path).status_code == 404
    assert http_client.post(f"{path}/execution", json={"inputs": VALID_INPUTS}).status_code == 404


def test_process_list_limit(http_client):
    assert len(http_client.get("/processes?limit=1").get_json()["processes"]) == 1
    assert http_client.get("/processes?limit=invalid").status_code == 400


@pytest.mark.parametrize("response_mode", ["raw", "document"])
def test_real_http_execution(http_server, response_mode):
    payload = json.dumps({"inputs": VALID_INPUTS, "response": response_mode}).encode()
    request = urllib.request.Request(
        f"{http_server}{EXECUTION_PATH}",
        data=payload,
        headers={"Content-Type": "application/json", "Prefer": "respond-async"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 200
        assert response.headers.get_content_type() == "application/json"
        assert "Location" not in response.headers
        result = json.load(response)
    Draft202012Validator(DOCUMENT_SCHEMA if response_mode == "document" else INFO_SCHEMA).validate(result)
