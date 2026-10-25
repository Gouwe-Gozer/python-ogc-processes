"""Manager capabilities affect only the API instance being described."""

import json
from copy import deepcopy

import pytest
from flask import Flask, request
from pygeoapi.api import API, APIRequest
from pygeoapi.api import conformance as upstream_conformance
from pygeoapi.api import processes as processes_api

from geo_processes.discovery import conformance
from geo_processes.manager import OgcSynchronousManager

CALLBACK = "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/callback"


def response(api, format_="json", handler=conformance):
    with Flask(__name__).test_request_context(f"/conformance?f={format_}"):
        api_request = APIRequest.from_flask(request, api.locales)
        headers, status, body = handler(api, api_request)
        assert api_request.format == format_
    assert status == 200
    assert headers["Content-Type"].startswith("application/json" if format_ == "json" else "text/html")
    return json.loads(body)["conformsTo"] if format_ == "json" else body


def callback_api(service_config, tmp_path):
    config = deepcopy(service_config)
    # No Features corrections: exercise Callback filtering independently.
    config["resources"] = {"raster-info": config["resources"]["raster-info"]}
    config["server"]["manager"] = {
        "name": "TinyDB",
        "connection": str(tmp_path / "jobs.json"),
        "output_dir": str(tmp_path),
    }
    return API(config, {})


def test_constructing_synchronous_managers_does_not_mutate_upstream_conformance():
    original = list(processes_api.CONFORMANCE_CLASSES)
    assert CALLBACK in original
    for _ in range(2):
        manager = OgcSynchronousManager({"name": "geo_processes.manager.OgcSynchronousManager"})
        assert manager.supports_subscribing is False
        assert original == processes_api.CONFORMANCE_CLASSES


@pytest.mark.parametrize("format_", ["json", "html"])
@pytest.mark.parametrize("is_async", [False, True])
@pytest.mark.parametrize("supports_subscribing", [False, True])
def test_callback_claim_uses_subscriber_capability_independently_of_execution_mode(
    service_config, tmp_path, format_, is_async, supports_subscribing
):
    api = callback_api(service_config, tmp_path)
    api.manager.is_async = is_async
    api.manager.supports_subscribing = supports_subscribing
    assert (CALLBACK in response(api, format_)) is supports_subscribing
    # The application filters a copy; the native implementation is untouched.
    assert CALLBACK in response(api, format_, handler=upstream_conformance)


@pytest.mark.parametrize("format_", ["json", "html"])
def test_api_instances_with_different_managers_keep_independent_callback_claims(service_config, tmp_path, format_):
    other_api = callback_api(service_config, tmp_path)
    before = response(other_api, format_)
    original = list(processes_api.CONFORMANCE_CLASSES)
    assert CALLBACK in before

    own_api = API(deepcopy(service_config), {})
    assert CALLBACK not in response(own_api, format_)
    assert response(other_api, format_) == before
    assert CALLBACK in response(own_api, format_, handler=upstream_conformance)
    assert original == processes_api.CONFORMANCE_CLASSES
