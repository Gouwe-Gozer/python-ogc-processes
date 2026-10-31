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
    pending_status = async_client.get(f"/jobs/{identifier}").json
    assert any(link["rel"] == "monitor" for link in pending_status["links"])
    assert manager.claim() == identifier
    assert async_client.get(f"/jobs/{identifier}").json["status"] == "running"
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
    validate_official(status.json, "statusInfo.yaml")
    assert "progress" not in status.json
    result = async_client.get(f"/jobs/{identifier}/results")
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


def test_default_remains_synchronous_and_optional_capabilities_are_not_advertised(async_client, durable):
    manager, config, _ = durable
    response = async_client.post("/processes/raster-info/execution", json={"inputs": {"source": DEMO_SOURCE}})
    assert response.status_code == 200 and "Location" not in response.headers
    assert manager.claim() is None
    description = async_client.get("/processes/raster-info?f=json").json
    assert description["jobControlOptions"] == ["sync-execute", "async-execute"]
    assert not any(link["rel"].endswith("/job-list") for link in description["links"])
    assert not any(link["rel"].endswith("/job-list") for link in async_client.get("/?f=json").json["links"])
    assert "Browse jobs" not in async_client.get("/?f=html").text
    assert manager.is_async is True
    assert not any(
        uri.endswith("/callback") or uri.endswith("/job-list")
        for uri in async_client.get("/conformance").json["conformsTo"]
    )
    assert async_client.get("/jobs").status_code == 405
    dismissal = async_client.delete("/jobs/unknown")
    assert dismissal.status_code == 405 and "DELETE" not in dismissal.headers["Allow"]
    assert async_client.options("/jobs/unknown").status_code == 204
    document = generate_openapi(config)
    assert validate_openapi_document(document)
    assert "/jobs" not in document["paths"]
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
