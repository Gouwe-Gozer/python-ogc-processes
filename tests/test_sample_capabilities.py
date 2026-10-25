"""Keep read-only sample discovery honest without changing process semantics."""

from copy import deepcopy

import pytest
from flask import request as flask_request
from pygeoapi.api import APIRequest
from pygeoapi.api import conformance as upstream_conformance
from pygeoapi.openapi import validate_openapi_document
from test_ogc_schemas import validate_official

from geo_processes.discovery import CALLBACK_CONFORMANCE_URI, CQL_CLASSES, FEATURES_CRUD


def test_json_and_html_conformance_omit_only_confirmed_unsupported_claims(http_client):
    import json

    from pygeoapi.flask_app import api_

    with http_client.application.test_request_context("/conformance?f=json"):
        request = APIRequest.from_flask(flask_request, api_.locales)
        original = json.loads(upstream_conformance(api_, request)[2])["conformsTo"]
    response = http_client.get("/conformance?f=json")
    assert response.status_code == 200
    document = response.get_json()
    validate_official(document, "confClasses.yaml")
    excluded = {CALLBACK_CONFORMANCE_URI, FEATURES_CRUD, *CQL_CLASSES}
    assert set(document["conformsTo"]) == set(original) - excluded
    html = http_client.get("/conformance?f=html")
    assert html.status_code == 200 and html.mimetype == "text/html"
    assert all(uri in html.text for uri in document["conformsTo"])
    assert not any(uri in html.text for uri in excluded)


def test_editable_configuration_preserves_upstream_claims(http_client, monkeypatch):
    from pygeoapi.flask_app import api_

    config = deepcopy(api_.config)
    config["resources"]["sample-points"]["providers"][0]["editable"] = True
    monkeypatch.setattr(api_, "config", config)
    classes = http_client.get("/conformance?f=json").get_json()["conformsTo"]
    assert {FEATURES_CRUD, *CQL_CLASSES} <= set(classes)


@pytest.mark.parametrize("collection", ["sample-points", "sample-polygons"])
def test_sample_openapi_keeps_reads_and_omits_unsupported_query_posts(http_client, collection):
    document = http_client.get("/openapi?f=json").get_json()
    assert validate_openapi_document(document)
    operation = document["paths"][f"/collections/{collection}/items"]
    assert "get" in operation and "options" in operation and "post" not in operation


@pytest.mark.parametrize("query", ["filter=id%3D%27point-1%27", "filter-lang=cql2-text", "filter-crs=CRS84"])
def test_unsupported_query_parameters_return_helpful_errors(http_client, query):
    response = http_client.get(f"/collections/sample-points/items?f=json&{query}")
    assert response.status_code == 400
    validate_official(response.get_json(), "exception.yaml")
    assert "use bbox or feature IDs" in response.get_json()["detail"]


def test_query_posts_are_rejected_instead_of_silently_returning_all_points(http_client):
    before = http_client.get("/collections/sample-points/items?f=json").get_json()["features"]
    response = http_client.post(
        "/collections/sample-points/items?f=json", json={"op": "=", "args": [{"property": "id"}, "point-1"]}
    )
    assert response.status_code == 400
    assert "CQL filtering is not supported" in response.get_json()["detail"]
    after = http_client.get("/collections/sample-points/items?f=json").get_json()["features"]
    assert after == before
    assert http_client.get("/collections/sample-points/items/point-1?f=json").get_json()["id"] == "point-1"
