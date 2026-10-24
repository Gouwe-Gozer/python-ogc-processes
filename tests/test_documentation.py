"""Use the upstream HTML endpoint with a compatible pinned ReDoc template."""

from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import pytest
from pygeoapi.util import TEMPLATESDIR

from geo_processes.documentation import configure_documentation_templates


class DocumentationElements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.spec_url = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script" and "src" in attributes:
            self.scripts.append(attributes)
        if tag == "redoc":
            self.spec_url = attributes.get("spec-url")


def test_redoc_endpoint_uses_pinned_classic_bundle_and_live_openapi(http_client):
    response = http_client.get("/openapi?f=html&ui=redoc")
    assert response.status_code == 200 and response.mimetype == "text/html"
    elements = DocumentationElements()
    elements.feed(response.text)
    assert elements.scripts == [{"src": "https://cdn.jsdelivr.net/npm/redoc@2.5.3/bundles/redoc.standalone.js"}]
    assert elements.spec_url == "http://example.test/openapi?f=json"
    spec = http_client.get("/openapi?f=json")
    assert spec.status_code == 200 and spec.get_json()["openapi"].startswith("3.")
    assert "/processes/raster-sample-points/execution" in spec.get_json()["paths"]
    assert "Download the OpenAPI document" in response.text


def test_redoc_spec_url_preserves_configured_prefix(http_client, monkeypatch):
    from pygeoapi.flask_app import api_

    monkeypatch.setattr(api_, "base_url", "https://example.test/geo")
    elements = DocumentationElements()
    elements.feed(http_client.get("/openapi?f=html&ui=redoc").text)
    assert elements.spec_url == "https://example.test/geo/openapi?f=json"


def test_other_html_templates_still_use_upstream_fallback(http_client):
    response = http_client.get("/openapi?f=html")
    assert response.status_code == 200 and response.mimetype == "text/html"
    assert "SwaggerUIBundle" in response.text and 'id="swagger-ui"' in response.text
    assert "redoc@2.5.3" not in response.text
    assert http_client.get("/?f=html").status_code == 200


@pytest.mark.parametrize("path", [str(TEMPLATESDIR), "/operator/custom-templates"])
def test_template_configuration_keeps_operator_overrides(path):
    config = {"server": {"templates": {"path": path, "static": "/assets"}}}
    api = SimpleNamespace(config=config, tpl_config=deepcopy(config))
    configure_documentation_templates(api)
    actual = api.config["server"]["templates"]
    assert actual["static"] == "/assets"
    assert actual == api.tpl_config["server"]["templates"]
    if path == str(TEMPLATESDIR):
        assert (Path(actual["path"]) / "openapi" / "redoc.html").is_file()
    else:
        assert actual["path"] == path
