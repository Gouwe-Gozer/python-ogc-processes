"""Validate actual HTTP documents against the official, offline OGC schemas."""

from pathlib import Path

import pytest
import yaml
from jsonschema import Draft4Validator
from raster_fixtures import DEMO_SOURCE, FORMATS
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4

from geo_processes.datasets import DEMO_RASTER

SCHEMA_BASE = "https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi/schemas/"
SCHEMA_ROOT = Path(__file__).parent / "schemas" / "ogc-processes-1.0"
REGISTRY = Registry().with_resources(
    (SCHEMA_BASE + path.name, Resource.from_contents(yaml.safe_load(path.read_text()), default_specification=DRAFT4))
    for path in SCHEMA_ROOT.glob("*.yaml")
)


def validate_official(document, name):
    Draft4Validator({"$ref": SCHEMA_BASE + name}, registry=REGISTRY, format_checker=FORMATS).validate(document)


@pytest.fixture()
def reference_source(monkeypatch):
    # Schema/response tests use a staged fixture; actual verified TLS transport
    # and both raster operations are exercised together in test_inputs.py.
    monkeypatch.setattr(
        "geo_processes.inputs._fetch", lambda _url, destination: destination.write_bytes(DEMO_RASTER.read_bytes())
    )
    return {"href": "https://example.test/dem.tif", "type": "image/tiff"}


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


def test_execute_and_results_match_official_schemas(http_client, reference_source):
    document = {"inputs": {"source": reference_source}, "response": "document"}
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


def test_warp_reference_matches_official_execute_and_results_schemas(http_client, reference_source):
    payload = {
        "inputs": {"source": reference_source, "target_crs": "EPSG:4326"},
        "response": "document",
        "outputs": {"result": {"transmissionMode": "reference"}},
    }
    validate_official(payload, "execute.yaml")
    response = http_client.post("/processes/raster-warp/execution", json=payload)
    assert response.status_code == 200
    validate_official(response.get_json(), "results.yaml")


def test_source_reference_request_matches_official_schema():
    validate_official(
        {"inputs": {"source": {"href": "https://example.com/dem.tif", "type": "image/tiff"}}}, "execute.yaml"
    )


@pytest.mark.parametrize("qualified", [False, True])
def test_inline_source_keeps_the_published_binary_schema_limitation(qualified):
    from jsonschema import ValidationError

    from geo_processes.contracts.sources import SOURCE_EXECUTE_SCHEMA

    source = DEMO_SOURCE if qualified else DEMO_SOURCE["value"]
    Draft4Validator(SOURCE_EXECUTE_SCHEMA, format_checker=FORMATS).validate(source)
    with pytest.raises(ValidationError):
        validate_official({"inputs": {"source": source}}, "execute.yaml")


@pytest.mark.parametrize("process", ["raster-info", "raster-warp"])
def test_raster_description_uses_ogc_binary_value_conventions(http_client, process):
    description = http_client.get(f"/processes/{process}?f=json").get_json()
    validate_official(description, "process.yaml")
    source = description["inputs"]["source"]
    schema = source["schema"]
    validate_official(schema, "schema.yaml")
    # Req. 49-50: describe the raster value, following the binary image schema
    # in official ProcessDescription.json. No union is needed for transport or
    # for media-type aliases of the same supported GeoTIFF format (req. 51).
    assert schema == {
        "type": "string",
        "format": "byte",
        "contentEncoding": "binary",
        "contentMediaType": "image/tiff",
    }
    assert "demo-dem" not in str(description)
    Draft4Validator(schema, format_checker=FORMATS).validate(DEMO_SOURCE["value"])
    assert not Draft4Validator(schema, format_checker=FORMATS).is_valid("demo-dem")


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
