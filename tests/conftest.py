"""Real pygeoapi application and loopback HTTP service fixtures."""

import threading
from pathlib import Path

import pytest
import yaml
from pygeoapi.util import yaml_load

from geo_processes.datasets import SAMPLE_DATA_DIR
from geo_processes.openapi import generate_openapi


@pytest.fixture(scope="session")
def service_config():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("PYGEOAPI_SERVER_URL", "http://example.test")
        environment.setenv("GEO_SAMPLE_DATA_DIR", str(SAMPLE_DATA_DIR))
        with Path("config/pygeoapi.yml").open() as source:
            config = yaml_load(source)
    config["server"]["url"] = "http://example.test"
    config["server"]["cors"] = False
    config["server"]["ogc_schemas_location"] = "https://schemas.opengis.net"
    return config


@pytest.fixture(scope="session")
def app(service_config, tmp_path_factory):
    temporary_directory = tmp_path_factory.mktemp("pygeoapi-http-contract")
    config_path = temporary_directory / "pygeoapi.yml"
    openapi_path = temporary_directory / "openapi.yml"
    config_path.write_text(yaml.safe_dump(service_config))
    openapi_path.write_text(yaml.safe_dump(generate_openapi(service_config)))
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("PYGEOAPI_CONFIG", str(config_path))
        environment.setenv("PYGEOAPI_OPENAPI", str(openapi_path))
        environment.setenv("GEO_OUTPUT_DIR", str(temporary_directory / "results"))
        environment.setenv("GEO_INPUT_TMPDIR", str(temporary_directory / "inputs"))
        from geo_processes.app import APP

        APP.config["TESTING"] = True
        yield APP


@pytest.fixture()
def http_client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def http_server(app):
    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    from pygeoapi.flask_app import api_

    previous_url = api_.manager.result_base_url
    api_.manager.result_base_url = url
    yield url
    api_.manager.result_base_url = previous_url
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
