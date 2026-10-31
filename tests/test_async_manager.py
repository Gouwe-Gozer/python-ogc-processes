"""Durable PostgreSQL/HTTP integration; use an explicitly disposable database."""

import os
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from jsonschema import Draft4Validator, ValidationError
from pygeoapi.openapi import validate_openapi_document
from pygeoapi.util import RequestedProcessExecutionMode
from raster_fixtures import DEMO_SOURCE, FORMATS
from sqlalchemy import create_engine, text
from test_ogc_schemas import validate_official

from geo_processes.async_manager import DurableProcessManager, job_limits
from geo_processes.contracts.warp import DOCUMENT_SCHEMA
from geo_processes.errors import InputBusyError
from geo_processes.openapi import generate_openapi

ASYNC = RequestedProcessExecutionMode.respond_async
DSN = os.environ.get("GEO_TEST_JOB_DSN")


@pytest.fixture()
def durable(service_config, tmp_path, monkeypatch):
    if not DSN:
        pytest.skip("set GEO_TEST_JOB_DSN to a disposable PostgreSQL database")
    schema = "test_jobs_" + uuid4().hex
    engine = create_engine(DSN)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    config = deepcopy(service_config)
    config["server"]["manager"] = {
        "name": "geo_processes.async_manager.DurableProcessManager",
        "connection": DSN,
        "output_dir": str(tmp_path),
        "options": {"search_path": [schema]},
    }
    definition = {**deepcopy(config["server"]["manager"]), "processes": config["resources"]}
    definition["processes"] = {
        key: resource for key, resource in config["resources"].items() if resource["type"] == "process"
    }
    monkeypatch.setenv("GEO_OUTPUT_DIR", str(tmp_path / "results"))
    monkeypatch.setenv("GEO_INPUT_TMPDIR", str(tmp_path / "inputs"))
    manager = DurableProcessManager(definition)
    manager.result_base_url = "http://example.test"
    yield manager, config, definition
    manager._engine.dispose()
    with engine.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    engine.dispose()


@pytest.fixture()
def async_client(app, http_client, durable, monkeypatch):
    from pygeoapi.flask_app import api_

    monkeypatch.setattr(api_, "manager", durable[0])
    return http_client


def enqueue(client, process="raster-info", **options):
    inputs = {"source": DEMO_SOURCE}
    if process == "raster-warp":
        inputs["target_crs"] = "EPSG:4326"
    response = client.post(
        f"/processes/{process}/execution", json={"inputs": inputs, **options}, headers={"Prefer": "respond-async"}
    )
    assert response.status_code == 201
    assert response.headers["Preference-Applied"] == "respond-async"
    assert response.headers["Location"].endswith("/jobs/" + response.json["jobID"])
    validate_official(response.json, "statusInfo.yaml")
    return response.json["jobID"]


@pytest.mark.parametrize("response_mode", ["raw", "document"])
def test_cite_echo_sync_and_async_results_contain_the_same_message(async_client, durable, response_mode):
    manager = durable[0]
    manager.processes["cite-echo"] = {"processor": {"name": "test_processes.cite_echo.CiteEchoProcessor"}}
    message = "teststring"
    document = {"inputs": {"message": message}, "outputs": {"message": {}}, "response": response_mode}
    synchronous = async_client.post("/processes/cite-echo/execution", json=document)
    assert synchronous.status_code == 200
    submitted = async_client.post("/processes/cite-echo/execution", json=document, headers={"Prefer": "respond-async"})
    assert submitted.status_code == 201
    identifier = submitted.json["jobID"]
    assert manager.claim() == identifier
    manager.perform(identifier)
    asynchronous = async_client.get(f"/jobs/{identifier}/results")
    assert asynchronous.status_code == 200
    assert asynchronous.headers["Content-Type"] == synchronous.headers["Content-Type"] == "application/json"
    expected = message if response_mode == "raw" else {"message": {"value": message}}
    assert asynchronous.json == synchronous.json == expected


@pytest.mark.parametrize("response_mode", ["raw", "document"])
def test_cite_echo_extended_results_match_across_execution_modes(async_client, durable, response_mode):
    from test_cite_validation import multipart_json

    manager = durable[0]
    manager.processes["cite-echo"] = {"processor": {"name": "test_processes.cite_echo.CiteEchoProcessor"}}
    values = {
        "message": "hello",
        "array": [1, 2, 3],
        "bbox": {"bbox": [4, 52, 5, 53]},
        "mixed": {"value": {"label": "Café"}},
    }
    document = {"inputs": values, "response": response_mode}
    expected = {**values, "mixed": values["mixed"]["value"]}
    synchronous = async_client.post("/processes/cite-echo/execution", json=document)
    assert synchronous.status_code == 200
    submitted = async_client.post("/processes/cite-echo/execution", json=document, headers={"Prefer": "respond-async"})
    assert submitted.status_code == 201
    identifier = submitted.json["jobID"]
    assert manager.claim() == identifier
    manager.perform(identifier)
    asynchronous = async_client.get(f"/jobs/{identifier}/results")
    assert asynchronous.status_code == 200
    assert asynchronous.mimetype == synchronous.mimetype
    if response_mode == "raw":
        assert multipart_json(asynchronous) == multipart_json(synchronous) == expected
    else:
        assert asynchronous.json == synchronous.json == {name: {"value": value} for name, value in expected.items()}


@pytest.mark.parametrize(
    "media_type,value",
    [
        ("text/plain", 'Native "text" & punctuation\n'),
        ("text/plain; charset=utf-8", "Café\n"),
        ("application/xml", '<result value="1">native</result>\n'),
        ("text/xml", "<result>native</result>"),
        ("image/svg+xml", '<svg xmlns="http://www.w3.org/2000/svg"/>'),
        ("application/json", 'Café </script><script>"quoted"</script> &lt;river&gt; \\u003c'),
    ],
)
def test_native_string_results_match_synchronous_execution(async_client, durable, media_type, value):
    manager = durable[0]
    manager.processes["native-text"] = {"processor": {"name": "test_processes.native_text.NativeTextProcessor"}}
    document = {"inputs": {"media_type": media_type, "value": value}}
    synchronous = async_client.post("/processes/native-text/execution", json=document)
    assert synchronous.status_code == 200
    submitted = async_client.post(
        "/processes/native-text/execution", json=document, headers={"Prefer": "respond-async"}
    )
    assert submitted.status_code == 201
    identifier = submitted.json["jobID"]
    assert manager.claim() == identifier
    manager.perform(identifier)
    asynchronous = async_client.get(f"/jobs/{identifier}/results")
    assert asynchronous.status_code == 200
    assert asynchronous.headers["Content-Type"] == synchronous.headers["Content-Type"] == media_type
    if media_type == "application/json":
        assert asynchronous.json == synchronous.json == value
        assert all(b"<" not in response.data and b">" not in response.data for response in (synchronous, asynchronous))
    else:
        assert asynchronous.data == synchronous.data == value.encode("utf-8")


@pytest.mark.parametrize(
    "process,response,transmission",
    [
        ("raster-info", "raw", "value"),
        ("raster-info", "document", "value"),
        ("raster-warp", "raw", "value"),
        ("raster-warp", "document", "value"),
        ("raster-warp", "raw", "reference"),
        ("raster-warp", "document", "reference"),
    ],
)
def test_stored_representations_survive_manager_recreation(async_client, durable, process, response, transmission):
    manager, _, definition = durable
    outputs = {"result": {"transmissionMode": transmission}} if process == "raster-warp" else None
    identifier = enqueue(async_client, process, response=response, **({"outputs": outputs} if outputs else {}))
    pending = async_client.get(f"/jobs/{identifier}/results")
    assert pending.status_code == 404 and pending.json["code"] == "ResultNotReady"
    assert pending.headers["Cache-Control"] == "no-store"
    pending_status = async_client.get(f"/jobs/{identifier}")
    assert pending_status.headers["Cache-Control"] == "no-store"
    assert any(link["rel"] == "monitor" for link in pending_status.json["links"])
    assert manager.claim() == identifier
    running_status = async_client.get(f"/jobs/{identifier}")
    assert running_status.json["status"] == "running"
    assert running_status.headers["Cache-Control"] == "no-store"
    running_results = async_client.get(f"/jobs/{identifier}/results")
    assert running_results.status_code == 404 and running_results.json["code"] == "ResultNotReady"
    assert running_results.headers["Cache-Control"] == "no-store"
    manager.perform(identifier)
    restored = DurableProcessManager(definition)
    try:
        assert restored.get_job(identifier)["status"] == "successful"
        assert restored.request(identifier)["inputs"]["source"] == DEMO_SOURCE
        assert restored.response(identifier) == manager.response(identifier)
        media, body = restored.get_job_result(identifier)
        assert media == restored.response(identifier)["media_type"]
        assert body is not None
    finally:
        restored._engine.dispose()
    status = async_client.get(f"/jobs/{identifier}")
    assert status.headers["Cache-Control"] == "no-store"
    validate_official(status.json, "statusInfo.yaml")
    assert "progress" not in status.json
    result = async_client.get(f"/jobs/{identifier}/results")
    assert result.headers["Cache-Control"] == "no-store"
    if response == "raw" and transmission == "reference":
        assert result.status_code == 204 and not result.data and "Content-Type" not in result.headers
        assert "/results/" in result.headers["Link"]
    else:
        assert result.status_code == 200
        if response == "document":
            if process == "raster-warp" and transmission == "value":
                Draft4Validator(DOCUMENT_SCHEMA, format_checker=FORMATS).validate(result.json)
                # Preserve the existing official base64 oneOf ambiguity; do not alter valid output.
                with pytest.raises(ValidationError):
                    validate_official(result.json, "results.yaml")
            else:
                validate_official(result.json, "results.yaml")
        elif process == "raster-warp":
            assert result.mimetype == "image/tiff" and result.data[:2] in (b"II", b"MM")
        else:
            assert result.json["size"][0] > 0


def test_failures_interruption_and_unknown_jobs_have_specific_contracts(async_client, durable):
    manager = durable[0]
    response = async_client.post(
        "/processes/raster-info/execution", json={"inputs": {"source": "bad"}}, headers={"Prefer": "respond-async"}
    )
    identifier = response.json["jobID"]
    manager.claim()
    manager.perform(identifier)
    failed = async_client.get(f"/jobs/{identifier}/results")
    assert failed.status_code == 400 and failed.json["code"] == "InvalidParameterValue"
    assert failed.headers["Cache-Control"] == "no-store"
    interrupted = enqueue(async_client)
    manager.claim()
    manager.fail_interrupted()
    assert async_client.get(f"/jobs/{interrupted}").json["status"] == "failed"
    assert async_client.get(f"/jobs/{interrupted}/results").status_code == 500
    # A late orphaned execution cannot turn an explicitly failed job successful.
    manager.finish(interrupted, {"body": "late result"})
    assert manager.get_job(interrupted)["status"] == "failed"
    for suffix in ("", "/results"):
        unknown = async_client.get("/jobs/unknown" + suffix)
        assert unknown.status_code == 404 and unknown.json["code"] == "NoSuchJob"
        assert unknown.headers["Cache-Control"] == "no-store"


def test_unavailable_stored_response_is_not_cacheable(async_client, durable):
    manager = durable[0]
    identifier = enqueue(async_client)
    assert manager.claim() == identifier
    assert manager.update_job(identifier, {"status": "successful"})
    response = async_client.get(f"/jobs/{identifier}/results")
    assert response.status_code == 500 and response.json["code"] == "NoApplicableCode"
    assert response.headers["Cache-Control"] == "no-store"


def test_default_remains_synchronous_and_only_supported_capabilities_are_advertised(async_client, durable):
    manager, config, _ = durable
    response = async_client.post("/processes/raster-info/execution", json={"inputs": {"source": DEMO_SOURCE}})
    assert response.status_code == 200 and "Location" not in response.headers
    assert manager.claim() is None
    description = async_client.get("/processes/raster-info?f=json").json
    assert description["jobControlOptions"] == ["sync-execute", "async-execute"]
    assert any(link["rel"].endswith("/job-list") for link in description["links"])
    assert any(link["rel"].endswith("/job-list") for link in async_client.get("/?f=json").json["links"])
    assert "Browse jobs" in async_client.get("/?f=html").text
    assert manager.is_async is True
    assert not any(uri.endswith("/callback") for uri in async_client.get("/conformance").json["conformsTo"])
    assert async_client.get("/jobs").status_code == 200
    dismissal = async_client.delete("/jobs/unknown")
    assert dismissal.status_code == 405 and "DELETE" not in dismissal.headers["Allow"]
    assert async_client.options("/jobs/unknown").status_code == 204
    document = generate_openapi(config)
    assert validate_openapi_document(document)
    assert "/jobs" in document["paths"]
    assert "delete" not in document["paths"]["/jobs/{jobId}"]
    assert "201" in document["paths"]["/processes/raster-info/execution"]["post"]["responses"]


def test_job_capacity_and_expiry_are_bounded(durable):
    manager = durable[0]
    manager.limits["GEO_JOB_MAX_COUNT"] = 1
    identifier = manager.execute_process("raster-info", {"source": DEMO_SOURCE}, execution_mode=ASYNC)[0]
    with pytest.raises(InputBusyError):
        manager.execute_process("raster-info", {"source": DEMO_SOURCE}, execution_mode=ASYNC)
    with manager._engine.begin() as connection:
        connection.execute(
            manager._sql("UPDATE {jobs} SET created = :old WHERE identifier = :id"),
            {"old": datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2), "id": identifier},
        )
    assert manager.execute_process("raster-info", {"source": DEMO_SOURCE}, execution_mode=ASYNC)[0] != identifier
    manager.limits["GEO_JOB_MAX_BYTES"] = 1
    with pytest.raises(InputBusyError):
        manager.execute_process("raster-info", {"source": DEMO_SOURCE}, execution_mode=ASYNC)


def test_job_settings_validate_bounds_without_a_database(monkeypatch):
    monkeypatch.setenv("GEO_JOB_TIMEOUT", "0")
    with pytest.raises(ValueError, match="GEO_JOB_TIMEOUT"):
        job_limits()


def test_nonfinite_input_is_rejected_before_persistence(async_client, durable):
    response = async_client.post(
        "/processes/raster-info/execution",
        json={"inputs": {"source": float("nan")}},
        headers={"Prefer": "respond-async"},
    )
    assert response.status_code == 400 and response.json["code"] == "InvalidParameterValue"
    assert durable[0].claim() is None


def test_result_capacity_failure_fits_reserved_headroom(durable):
    import json

    manager = durable[0]
    request = {"inputs": {"source": DEMO_SOURCE}, "outputs": None, "response": "raw"}
    maximum = len(json.dumps(request).encode()) + 4096 + 100
    manager.limits["GEO_JOB_MAX_BYTES"] = maximum
    identifier = manager.execute_process("raster-info", request["inputs"], execution_mode=ASYNC)[0]
    assert manager.claim() == identifier
    manager.finish(identifier, {"body": "x" * maximum})
    assert manager.get_job(identifier)["status"] == "failed"
    assert manager.response(identifier)["status"] == 503
    with manager._engine.connect() as connection:
        size = connection.execute(
            manager._sql("SELECT sum(octet_length(request) + octet_length(response)) FROM {jobs}")
        ).scalar_one()
    assert size <= maximum


@pytest.mark.parametrize(
    "response_mode,transmission",
    [("raw", "value"), ("document", "value"), ("raw", "reference"), ("document", "reference")],
)
def test_sampling_properties_survive_sync_and_async_result_delivery(async_client, durable, response_mode, transmission):
    from urllib.parse import urlsplit

    from test_raster_operations import points, raster_source

    features = points([[4.5, 53.5]])
    properties = {
        "label": "</script><script>alert('Café')</script>",
        "entity": "&lt;river&gt; &amp; &#60;",
        "nested": {"key<tag>": ["a < b > c", r"\u003c", 7, None]},
    }
    features["features"][0]["properties"] = properties
    document = {
        "inputs": {"source": raster_source(), "points": {"value": features, "mediaType": "application/geo+json"}},
        "response": response_mode,
        "outputs": {"result": {"transmissionMode": transmission}},
    }
    path = "/processes/raster-sample-points/execution"
    synchronous = async_client.post(path, json=document)
    submitted = async_client.post(path, json=document, headers={"Prefer": "respond-async"})
    assert submitted.status_code == 201
    identifier = submitted.json["jobID"]
    assert durable[0].claim() == identifier
    durable[0].perform(identifier)
    asynchronous = async_client.get(f"/jobs/{identifier}/results")
    for response in (synchronous, asynchronous):
        if response_mode == "raw" and transmission == "reference":
            assert response.status_code == 204 and response.data == b"" and "Content-Type" not in response.headers
            href = response.headers["Link"].split(">", 1)[0][1:]
            result = async_client.get(urlsplit(href).path)
            assert result.status_code == 200 and result.mimetype == "application/geo+json"
            result = result.json
        else:
            assert response.status_code == 200
            if response_mode == "document":
                assert response.mimetype == "application/json"
                assert b"<" not in response.data and b">" not in response.data
                value = response.json["result"]
                if transmission == "reference":
                    download = async_client.get(urlsplit(value["href"]).path)
                    assert download.status_code == 200 and download.mimetype == "application/geo+json"
                    result = download.json
                else:
                    result = value["value"]
            else:
                assert response.mimetype == "application/geo+json"
                result = response.json
        assert result["features"][0]["properties"] == {**properties, "value": 1}
