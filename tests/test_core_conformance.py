"""Core requirements 1–46, scoped to the offered synchronous processes."""

from html.parser import HTMLParser
from urllib.parse import urlsplit

import pytest
from pygeoapi.openapi import validate_openapi_document
from pygeoapi.process.manager.tinydb_ import TinyDBManager
from raster_fixtures import DEMO_SOURCE
from test_ogc_schemas import validate_official

from geo_processes.discovery import CONFORMANCE_REL
from geo_processes.errors import OGC_EXCEPTIONS


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))


def local_path(url):
    parsed = urlsplit(url)
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


def test_landing_page_contains_required_core_relations_and_live_definitions(http_client):
    response = http_client.get("/?f=json")
    assert response.status_code == 200
    document = response.get_json()
    validate_official(document, "landingPage.yaml")
    links = {link["rel"]: link for link in document["links"]}
    assert {"service-desc", CONFORMANCE_REL, "http://www.opengis.net/def/rel/ogc/1.0/processes"} <= links.keys()
    for relation in ("service-desc", "service-doc"):
        definition = http_client.get(local_path(links[relation]["href"]))
        assert definition.status_code == 200
        if relation == "service-desc":
            assert validate_openapi_document(definition.get_json())
    html = http_client.get("/?f=html")
    assert html.status_code == 200
    parser = Links()
    parser.feed(html.text)
    assert CONFORMANCE_REL in {link.get("rel") for link in parser.links}


@pytest.mark.parametrize(
    "path,headers",
    [
        ("/?f=jsonld", {}),
        ("/", {"Accept": "application/ld+json"}),
    ],
)
def test_jsonld_landing_preserves_upstream_catalog_and_adds_http_links(app, http_client, monkeypatch, path, headers):
    from geo_processes.app import apply_process_status

    with monkeypatch.context() as context:
        context.setitem(
            app.after_request_funcs,
            None,
            [callback for callback in app.after_request_funcs[None] if callback is not apply_process_status],
        )
        upstream = http_client.get(path, headers=headers)
    response = http_client.get(path, headers=headers)
    assert response.status_code == upstream.status_code == 200
    assert response.mimetype == "application/ld+json"
    assert response.data == upstream.data
    document = response.get_json()
    assert document["@type"] == "DataCatalog" and document["name"] == "Raster Processes API"
    assert "links" not in document
    link_headers = ", ".join(response.headers.getlist("Link"))
    assert f'rel="{CONFORMANCE_REL}"' in link_headers
    assert 'rel="service-desc"' in link_headers


@pytest.mark.parametrize(
    "format_,accept,media_type",
    [
        ("json", "application/ld+json", "application/json"),
        ("html", "application/ld+json", "text/html"),
        ("jsonld", "text/html", "application/ld+json"),
    ],
)
def test_landing_query_format_overrides_accept(http_client, format_, accept, media_type):
    response = http_client.get(f"/?f={format_}", headers={"Accept": accept})
    assert response.status_code == 200 and response.mimetype == media_type
    if format_ == "json":
        validate_official(response.get_json(), "landingPage.yaml")
        assert any(link["rel"] == CONFORMANCE_REL for link in response.get_json()["links"])
    assert CONFORMANCE_REL in ", ".join(response.headers.getlist("Link"))


@pytest.mark.parametrize("document", [{"title": "Other response"}, [], None, {"links": None}])
def test_landing_link_hook_preserves_other_json_shapes(app, document):
    from flask import jsonify
    from pygeoapi.flask_app import api_

    from geo_processes.discovery import landing_links

    with app.app_context():
        response = jsonify(document)
        original_body = response.data
        assert landing_links(response, api_) is response
        assert response.data == original_body


def test_limited_process_list_can_be_traversed_without_losing_filters(http_client):
    response = http_client.get("/processes?limit=1&f=json")
    assert response.status_code == 200
    first = response.get_json()
    validate_official(first, "processList.yaml")
    links = {link["rel"]: link for link in first["links"] if link["rel"] != "alternate"}
    again = http_client.get(local_path(links["self"]["href"])).get_json()
    assert again == first
    second = http_client.get(local_path(links["next"]["href"])).get_json()
    validate_official(second, "processList.yaml")
    assert len(first["processes"]) == len(second["processes"]) == 1
    assert first["processes"][0]["id"] != second["processes"][0]["id"]
    seen = {first["processes"][0]["id"], second["processes"][0]["id"]}
    page = second
    while next_link := next((link for link in page["links"] if link["rel"] == "next"), None):
        page = http_client.get(local_path(next_link["href"])).get_json()
        validate_official(page, "processList.yaml")
        identifier = page["processes"][0]["id"]
        assert identifier not in seen
        seen.add(identifier)
    assert seen == {"raster-info", "raster-warp", "raster-sample-points", "raster-reclassify", "raster-polygonize"}
    for link in first["links"]:
        alternate = http_client.get(local_path(link["href"]))
        assert alternate.status_code == 200
        if link["rel"] == "alternate" and link["type"] == "text/html":
            parser = Links()
            parser.feed(alternate.text)
            assert any(item.get("rel") == "next" for item in parser.links)
    assert 'rel="next"' in response.headers["Link"]


@pytest.mark.parametrize("query", ["limit=0", "limit=-1", "limit=1.5", "limit=x", "offset=-1", "offset=1.5"])
def test_invalid_pagination_is_a_controlled_client_error(http_client, query):
    response = http_client.get(f"/processes?{query}")
    assert response.status_code == 400
    validate_official(response.get_json(), "exception.yaml")


def test_listing_honors_default_maximum_and_offset_for_a_larger_catalogue(http_client, monkeypatch):
    from pygeoapi.flask_app import api_

    definition = next(iter(api_.manager.processes.values()))
    monkeypatch.setattr(api_.manager, "processes", {f"operation-{index}": definition for index in range(60)})
    default = http_client.get("/processes").get_json()
    maximum = http_client.get("/processes?limit=99999").get_json()
    assert len(default["processes"]) == 10
    assert len(maximum["processes"]) == 50
    remaining = http_client.get("/processes?limit=50&offset=50").get_json()
    assert len(remaining["processes"]) == 10
    assert not any(link["rel"] == "next" for link in remaining["links"])


@pytest.mark.parametrize("path", ["/jobs/unknown", "/jobs/unknown/results"])
@pytest.mark.parametrize("format_", ["json", "html"])
def test_unknown_jobs_have_the_required_exception_type_in_each_encoding(http_client, path, format_):
    response = http_client.get(f"{path}?f={format_}")
    assert response.status_code == 404
    uri = f"{OGC_EXCEPTIONS}/no-such-job"
    if format_ == "json":
        document = response.get_json()
        validate_official(document, "exception.yaml")
        assert document["type"] == uri
        assert document["code"] == "NoSuchJob"
    else:
        assert response.mimetype == "text/html"
        assert uri in response.text


@pytest.mark.parametrize("path", ["/processes/unknown", "/processes/unknown/execution"])
def test_unknown_process_html_exposes_the_required_exception_uri(http_client, path):
    response = (
        http_client.post(path + "?f=html", json={"inputs": {}})
        if path.endswith("execution")
        else http_client.get(path + "?f=html")
    )
    assert response.status_code == 404
    assert f"{OGC_EXCEPTIONS}/no-such-process" in response.text


def test_job_corrections_work_with_the_existing_async_manager(http_client, monkeypatch, tmp_path):
    from pygeoapi.flask_app import api_

    manager = TinyDBManager({"name": "TinyDB", "connection": str(tmp_path / "jobs.json")})
    manager.add_job({"identifier": "running-job", "status": "running"})
    monkeypatch.setattr(api_, "manager", manager)
    response = http_client.get("/jobs/running-job/results?f=json")
    assert response.status_code == 404
    assert response.get_json()["type"] == f"{OGC_EXCEPTIONS}/result-not-ready"
    missing = http_client.get("/jobs/missing?f=json")
    assert missing.status_code == 404
    assert missing.get_json()["type"] == f"{OGC_EXCEPTIONS}/no-such-job"


def test_html_exception_text_is_escaped(app):
    from pygeoapi.flask_app import api_

    with app.test_request_context():
        headers, status, body = api_.get_exception(400, {}, "html", "InvalidParameterValue", "<script>bad()</script>")
    assert status == 400 and headers["Content-Type"] == "text/html"
    assert "<script>" not in body and "&lt;script&gt;" in body


def test_sync_success_does_not_create_or_advertise_a_persistent_job(http_client):
    response = http_client.post("/processes/raster-info/execution", json={"inputs": {"source": DEMO_SOURCE}})
    assert response.status_code == 200
    assert "Location" not in response.headers
    assert "monitor" not in response.headers.get("Link", "")
    paths = http_client.get("/openapi?f=json").get_json()["paths"]
    assert "/jobs" not in paths
    for path in ("/jobs/{jobID}", "/jobs/{jobID}/results"):
        operation = paths[path]
        assert set(operation) == {"get"}
        assert "200" not in operation["get"]["responses"]
        validate_official(
            operation["get"]["responses"]["404"]["content"]["application/json"]["example"], "exception.yaml"
        )


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_unsupported_execution_methods_are_405(http_client, method):
    response = getattr(http_client, method)("/processes/raster-info/execution", json={"inputs": {}})
    assert response.status_code == 405
    assert "POST" in response.headers["Allow"]
