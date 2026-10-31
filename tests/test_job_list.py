"""Job-list HTTP integration over the existing disposable PostgreSQL fixture."""

from datetime import UTC, datetime, timedelta

import pytest
from raster_fixtures import DEMO_SOURCE
from test_async_manager import async_client as async_client
from test_async_manager import durable as durable
from test_async_manager import enqueue
from test_ogc_schemas import validate_official


def test_job_list_empty_response_has_schema_links_and_safe_metadata(async_client, durable):
    response = async_client.get("/jobs?f=json")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.mimetype == "application/json"
    validate_official(response.json, "jobList.yaml")
    assert response.json["jobs"] == []
    assert {link["rel"] for link in response.json["links"]} == {"self", "alternate"}
    identifier = enqueue(async_client)
    listed = async_client.get("/jobs").json["jobs"]
    assert [job["jobID"] for job in listed] == [identifier]
    assert listed[0] == async_client.get(f"/jobs/{identifier}").json
    assert not {"request", "response", "location", "mimetype", "output", "parameters"} & set(listed[0])
    validate_official(listed[0], "statusInfo.yaml")


@pytest.fixture()
def listed_jobs(async_client, durable):
    manager = durable[0]
    origin = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=20)
    rows = {}
    for index, (name, process, status, seconds) in enumerate(
        [
            ("accepted", "raster-info", "accepted", None),
            ("running", "raster-warp", "running", None),
            ("successful", "raster-info", "successful", 4),
            ("failed", "raster-warp", "failed", 6),
            ("incomplete", "raster-info", "failed", None),
            ("expired", "raster-info", "successful", 4),
        ]
    ):
        identifier = enqueue(async_client, process)
        created = origin + timedelta(seconds=index)
        started = (
            datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=8)
            if name == "running"
            else (created if seconds is not None else None)
        )
        finished = started + timedelta(seconds=seconds) if seconds is not None else None
        if name == "expired":
            created -= timedelta(days=2)
        assert manager.update_job(
            identifier, {"created": created, "started": started, "finished": finished, "status": status}
        )
        rows[name] = {"id": identifier, "created": created}
    return rows


@pytest.mark.parametrize(
    "query,names",
    [
        ({}, ["accepted", "running", "successful", "failed", "incomplete"]),
        ({"type": "process"}, ["accepted", "running", "successful", "failed", "incomplete"]),
        ({"type": "other"}, []),
        ({"type": "other,process"}, ["accepted", "running", "successful", "failed", "incomplete"]),
        ({"processID": "raster-warp"}, ["running", "failed"]),
        ({"processID": "unknown"}, []),
        ({"processID": "raster-info') OR true --"}, []),
        ({"status": "accepted,failed"}, ["accepted", "failed", "incomplete"]),
        ([("status", "running"), ("status", "successful")], ["running", "successful"]),
        ({"status": "unknown"}, []),
        (
            {"processID": "raster-info,raster-warp", "status": "successful,failed"},
            ["successful", "failed", "incomplete"],
        ),
        ({"minDuration": "5"}, ["running", "failed"]),
        ({"maxDuration": "7"}, ["successful", "failed"]),
        ({"minDuration": "5", "maxDuration": "7"}, ["failed"]),
        ({"minDuration": "3,5"}, ["running", "failed"]),
        ({"maxDuration": "7,5"}, ["successful"]),
        ({"minDuration": "5", "maxDuration": "4"}, []),
        ({"status": "accepted", "minDuration": "0"}, []),
    ],
)
def test_job_list_filters(async_client, listed_jobs, query, names):
    response = async_client.get("/jobs", query_string=query)
    assert response.status_code == 200
    validate_official(response.json, "jobList.yaml")
    assert [row["jobID"] for row in response.json["jobs"]] == [listed_jobs[name]["id"] for name in names]


@pytest.mark.parametrize(
    "mode,names",
    [
        ("instant", ["successful"]),
        ("offset_instant", ["successful"]),
        ("closed", ["running", "successful", "failed"]),
        ("open_start", ["accepted", "running"]),
        ("open_end", ["failed", "incomplete"]),
        ("empty_start", ["accepted", "running"]),
        ("empty_end", ["failed", "incomplete"]),
    ],
)
def test_job_list_datetime_filters(async_client, listed_jobs, mode, names):
    def stamp(name):
        return listed_jobs[name]["created"].replace(tzinfo=UTC).isoformat()

    values = {
        "instant": stamp("successful"),
        "offset_instant": (listed_jobs["successful"]["created"] + timedelta(hours=1)).isoformat() + "+01:00",
        "closed": stamp("running") + "/" + stamp("failed"),
        "open_start": "../" + stamp("running"),
        "open_end": stamp("failed") + "/..",
        "empty_start": "/" + stamp("running"),
        "empty_end": stamp("failed") + "/",
    }
    response = async_client.get("/jobs", query_string={"datetime": values[mode]})
    assert response.status_code == 200
    assert [row["jobID"] for row in response.json["jobs"]] == [listed_jobs[name]["id"] for name in names]


@pytest.mark.parametrize(
    "query",
    [
        {"limit": "0"},
        {"limit": "-1"},
        {"limit": "1.5"},
        {"offset": "-1"},
        {"offset": "1.5"},
        [("limit", "1"), ("limit", "2")],
        {"unknown": "true"},
        {"status": ""},
        {"status": "running,"},
        {"minDuration": "1.5"},
        {"maxDuration": "NaN"},
        {"minDuration": ""},
        {"datetime": "../.."},
        {"datetime": "2026-01-01"},
        {"datetime": "2026-01-01T00:00:00"},
        {"datetime": "2026-02-30T00:00:00Z"},
        {"datetime": "2026-02-01T00:00:00Z/2026-01-01T00:00:00Z"},
    ],
)
def test_job_list_invalid_filters_return_controlled_errors(async_client, query):
    response = async_client.get("/jobs", query_string=query)
    assert response.status_code == 400
    assert response.json["code"] == "InvalidParameterValue"
    assert response.headers["Cache-Control"] == "no-store"
    validate_official(response.json, "exception.yaml")


def test_job_list_pagination_preserves_filters_and_html_links(async_client, listed_jobs):
    response = async_client.get("/jobs?processID=raster-info&limit=1")
    seen = []
    for index in range(3):
        assert response.status_code == 200
        seen += [row["jobID"] for row in response.json["jobs"]]
        assert len(response.json["jobs"]) == 1
        links = {link["rel"]: link for link in response.json["links"]}
        assert "processID=raster-info" in links["self"]["href"]
        alternate = async_client.get(links["alternate"]["href"])
        assert alternate.status_code == 200 and alternate.mimetype == "text/html"
        assert response.json["jobs"][0]["jobID"] in alternate.text
        if index < 2:
            response = async_client.get(links["next"]["href"])
        else:
            assert "next" not in links and "prev" in links
    assert seen == [listed_jobs[name]["id"] for name in ["accepted", "successful", "incomplete"]]
    empty = async_client.get("/jobs?offset=999999999999999999999999")
    assert empty.status_code == 200 and empty.json["jobs"] == []


def test_job_list_advertisement_and_submission_metadata_match_the_contract(async_client, durable):
    from pygeoapi.openapi import validate_openapi_document

    from geo_processes.openapi import generate_openapi

    submission = async_client.post(
        "/processes/raster-info/execution",
        json={"inputs": {"source": DEMO_SOURCE}},
        headers={"Prefer": "respond-async"},
    )
    assert submission.status_code == 201 and submission.json["processID"] == "raster-info"
    uri = "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/job-list"
    assert uri in async_client.get("/conformance").json["conformsTo"]
    assert any(link["rel"].endswith("/job-list") for link in async_client.get("/?f=json").json["links"])
    assert any(
        link["rel"].endswith("/job-list") for link in async_client.get("/processes/raster-info?f=json").json["links"]
    )
    assert "Browse jobs" in async_client.get("/?f=html").text
    specification = generate_openapi(durable[1])
    assert validate_openapi_document(specification)
    operation = specification["paths"]["/jobs"]["get"]
    parameters = {item["name"]: item for item in operation["parameters"]}
    assert {"type", "processID", "status", "datetime", "minDuration", "maxDuration", "limit", "offset"} <= set(
        parameters
    )
    for name in ("type", "processID", "status", "minDuration", "maxDuration"):
        assert parameters[name]["schema"]["type"] == "array"
        assert parameters[name]["explode"] is (name != "maxDuration")
    assert parameters["limit"]["schema"]["maximum"] == durable[1]["server"]["limits"]["max_items"]
    assert "delete" not in specification["paths"]["/jobs/{jobId}"]


def test_job_list_survives_manager_recreation(async_client, durable, monkeypatch):
    from pygeoapi.flask_app import api_

    from geo_processes.async_manager import DurableProcessManager

    identifier = enqueue(async_client)
    assert durable[0].claim() == identifier
    durable[0].perform(identifier)
    before = async_client.get("/jobs").json
    replacement = DurableProcessManager(durable[2])
    try:
        monkeypatch.setattr(api_, "manager", replacement)
        assert async_client.get("/jobs").json == before
        assert async_client.get(f"/jobs/{identifier}/results").status_code == 200
    finally:
        replacement._engine.dispose()


def test_job_list_limits_head_and_expiry(async_client, listed_jobs, monkeypatch):
    from pygeoapi.flask_app import api_

    monkeypatch.setitem(api_.config["server"], "limits", {"default_items": 2, "max_items": 3})
    default = async_client.get("/jobs")
    assert len(default.json["jobs"]) == 2
    capped = async_client.get("/jobs?limit=999")
    assert len(capped.json["jobs"]) == 3
    assert "limit=3" in capped.json["links"][0]["href"]
    assert async_client.get(f"/jobs/{listed_jobs['expired']['id']}").status_code == 404
    head = async_client.head("/jobs")
    assert head.status_code == 200 and not head.data
    assert head.headers["Cache-Control"] == "no-store" and 'rel="alternate"' in head.headers["Link"]
    assert async_client.options("/jobs").status_code == 204
    assert async_client.get("/jobs?f=xml").status_code == 400


def test_job_list_links_use_configured_public_base_url(async_client, listed_jobs, monkeypatch):
    from pygeoapi.flask_app import api_

    base = "https://raster.example.test/api"
    monkeypatch.setattr(api_, "base_url", base)
    response = async_client.get("/jobs?limit=1")
    assert all(link["href"].startswith(base + "/jobs?") for link in response.json["links"])
    assert all(link["href"].startswith(base + "/jobs/") for link in response.json["jobs"][0]["links"])


def test_job_list_database_failure_is_sanitized_and_not_cached(async_client, durable, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    def unavailable(**kwargs):
        raise SQLAlchemyError("private database credentials and query")

    monkeypatch.setattr(durable[0], "get_jobs", unavailable)
    response = async_client.get("/jobs")
    assert response.status_code == 503
    assert response.json["code"] == "ServerBusy"
    assert "private database" not in response.text
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("format_", ["json", "html", "jsonld"])
@pytest.mark.parametrize("path", ["/", "/processes/raster-info"])
def test_durable_discovery_preserves_native_pygeoapi_responses(async_client, durable, monkeypatch, path, format_):
    from pygeoapi.flask_app import get_processes, landing_page

    response = async_client.get(f"{path}?f={format_}")
    # Native rendering remains authoritative; retain application after-request corrections.
    with monkeypatch.context() as context:
        context.setitem(async_client.application.view_functions, "pygeoapi.landing_page", landing_page)
        context.setitem(async_client.application.view_functions, "pygeoapi.get_processes", get_processes)
        native = async_client.get(f"{path}?f={format_}")
    assert response.status_code == native.status_code == 200
    assert response.headers["Content-Type"] == native.headers["Content-Type"]
    assert response.data == native.data
    assert response.headers.getlist("Link") == native.headers.getlist("Link")
    assert durable[0].is_async is True and durable[0].supports_job_list is True
