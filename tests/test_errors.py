"""Exception semantics across boundary guards, upstream routes and processors."""

import pytest
from raster_fixtures import DEMO_SOURCE
from test_ogc_schemas import validate_official

from geo_processes import engine
from geo_processes.errors import EXCEPTIONS
from geo_processes.inputs import RasterInputBusyError
from geo_processes.storage import ResultStoreError


def assert_exception(response, status, code):
    assert response.status_code == status
    assert response.content_type == "application/json"
    document = response.get_json()
    validate_official(document, "exception.yaml")
    assert document["type"] == EXCEPTIONS[code].uri
    assert document["code"] == code
    assert document["status"] == status
    assert document["detail"] == document["description"]
    assert document["detail"] and document["title"]
    return document


@pytest.mark.parametrize("execution", [False, True])
def test_unknown_process_has_the_requirement_15_uri(http_client, execution):
    path = "/processes/unknown"
    response = http_client.post(path + "/execution", json={"inputs": {}}) if execution else http_client.get(path)
    document = assert_exception(response, 404, "NoSuchProcess")
    assert document["type"] == "http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/no-such-process"


@pytest.mark.parametrize("payload", [[], {"inputs": {}}, {"inputs": {"source": "demo-dem"}}])
def test_boundary_and_processor_errors_use_the_same_catalogue(http_client, payload):
    response = http_client.post("/processes/raster-info/execution", json=payload)
    assert_exception(response, 400, "InvalidParameterValue")


def test_upstream_limit_error_uses_the_catalogue(http_client):
    assert_exception(http_client.get("/processes?limit=invalid"), 400, "InvalidParameterValue")


def test_oversized_execution_uses_the_catalogue(app, http_client, monkeypatch):
    monkeypatch.setitem(app.config, "MAX_CONTENT_LENGTH", 10)
    response = http_client.post("/processes/raster-info/execution", json={"inputs": {"source": DEMO_SOURCE}})
    assert_exception(response, 413, "RequestTooLarge")


def test_busy_inputs_use_the_catalogue(http_client, monkeypatch):
    def busy(*args, **kwargs):
        raise RasterInputBusyError("temporary raster input capacity is busy; retry later")

    monkeypatch.setattr("geo_processes.processes.info.resolve_source", busy)
    response = http_client.post("/processes/raster-info/execution", json={"inputs": {"source": DEMO_SOURCE}})
    assert_exception(response, 503, "ServerBusy")


def test_processing_failure_is_sanitized_and_classified(http_client, monkeypatch):
    def fail(*args, **kwargs):
        raise engine.RasterInfoError("/private/path/password.tif")

    monkeypatch.setattr(engine, "raster_info", fail)
    response = http_client.post("/processes/raster-info/execution", json={"inputs": {"source": DEMO_SOURCE}})
    assert_exception(response, 500, "NoApplicableCode")
    assert "password" not in response.text


def test_missing_result_is_distinct_from_an_ogc_job(http_client):
    document = assert_exception(http_client.get("/results/missing/output.tif"), 404, "NoSuchResult")
    assert "no-such-job" not in document["type"]


def test_result_storage_failure_is_sanitized(http_client, monkeypatch):
    def fail(*args, **kwargs):
        raise ResultStoreError("/private/storage/password")

    monkeypatch.setattr("geo_processes.storage.ResultStore.read", fail)
    response = http_client.get("/results/missing/output.tif")
    assert_exception(response, 500, "NoApplicableCode")
    assert "password" not in response.text


def test_openapi_advertises_exception_uris_and_schemas(http_client):
    paths = http_client.get("/openapi?f=json").get_json()["paths"]
    for process in ("raster-info", "raster-warp"):
        responses = paths[f"/processes/{process}/execution"]["post"]["responses"]
        for status in ("400", "404", "413", "500", "503"):
            content = responses[status]["content"]["application/json"]
            assert content["schema"]["$ref"].endswith("/exception.yaml")
            validate_official(content["example"], "exception.yaml")
            assert content["example"]["status"] == int(status)
