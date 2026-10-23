"""Validate actual HTTP documents against the official, offline OGC schemas."""

import base64
import binascii
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft4Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4

SCHEMA_BASE = "https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi/schemas/"
SCHEMA_ROOT = Path(__file__).parent / "schemas" / "ogc-processes-1.0"
REGISTRY = Registry().with_resources(
    (SCHEMA_BASE + path.name, Resource.from_contents(yaml.safe_load(path.read_text()), default_specification=DRAFT4))
    for path in SCHEMA_ROOT.glob("*.yaml")
)
FORMATS = FormatChecker()


@FORMATS.checks("byte", raises=(ValueError, binascii.Error))
def is_base64(value):
    # OGC's inline string and binary branches use oneOf. OpenAPI's byte
    # format must be checked or every string incorrectly matches both.
    if not isinstance(value, str):
        return True
    base64.b64decode(value, validate=True)
    return True


def validate_official(document, name):
    Draft4Validator({"$ref": SCHEMA_BASE + name}, registry=REGISTRY, format_checker=FORMATS).validate(document)


@pytest.mark.parametrize(
    ("path", "schema"),
    [
        ("/conformance", "confClasses.yaml"),
        ("/processes", "processList.yaml"),
        ("/processes/raster-info", "process.yaml"),
        ("/processes/raster-warp", "process.yaml"),
    ],
)
def test_discovery_matches_official_schemas(http_client, path, schema):
    response = http_client.get(f"{path}?f=json")
    assert response.status_code == 200
    validate_official(response.get_json(), schema)


def test_execute_and_results_match_official_schemas(http_client):
    document = {"inputs": {"source": "demo-dem"}, "response": "document"}
    validate_official(document, "execute.yaml")
    response = http_client.post("/processes/raster-info/execution", json=document)
    assert response.status_code == 200
    validate_official(response.get_json(), "results.yaml")


def test_errors_match_official_schema(http_client):
    response = http_client.post("/processes/raster-info/execution", json={"inputs": {"source": "unknown"}})
    assert response.status_code == 400
    validate_official(response.get_json(), "exception.yaml")


def test_boundary_guard_is_required_by_pinned_upstream(app, http_client, monkeypatch):
    # Without our guard, upstream calls .get on this JSON list and raises.
    monkeypatch.setitem(app.before_request_funcs, None, [])
    with pytest.raises(AttributeError):
        http_client.post("/processes/raster-info/execution", json=[])


def test_warp_reference_matches_official_execute_and_results_schemas(http_client):
    payload = {
        "inputs": {"source": "demo-dem", "target_crs": "EPSG:4326"},
        "response": "document",
        "outputs": {"result": {"transmissionMode": "reference"}},
    }
    validate_official(payload, "execute.yaml")
    response = http_client.post("/processes/raster-warp/execution", json=payload)
    assert response.status_code == 200
    validate_official(response.get_json(), "results.yaml")


def test_official_binary_schema_has_overlapping_string_branches():
    # The unchanged official oneOf includes both an unrestricted string and
    # a byte-formatted string. Valid base64 therefore matches both, even with
    # format checking. Keep the correct base64 representation and record this
    # schema limitation instead of distorting binary output to pass a validator.
    value = "SUkrAA=="
    binary = Draft4Validator({"$ref": SCHEMA_BASE + "binaryInputValue.yaml"}, registry=REGISTRY, format_checker=FORMATS)
    assert binary.is_valid(value)
    assert Draft4Validator({"type": "string"}).is_valid(value)
    no_object = Draft4Validator(
        {"$ref": SCHEMA_BASE + "inputValueNoObject.yaml"}, registry=REGISTRY, format_checker=FORMATS
    )
    assert not no_object.is_valid(value)
