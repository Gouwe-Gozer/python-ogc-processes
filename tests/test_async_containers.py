"""Opt-in release-container lifecycle checks against disposable PostgreSQL volumes.

Run GEO_TEST_ASYNC_CONTAINERS=1 uv run pytest tests/test_async_containers.py -v.
Only uniquely named raster-async-test-* resources are created/restarted/removed.
"""

import base64
import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest
import requests
import yaml
from jsonschema import Draft4Validator, ValidationError
from raster_fixtures import DEMO_SOURCE, FORMATS
from test_ogc_schemas import validate_official

from geo_processes.contracts.warp import DOCUMENT_SCHEMA

pytestmark = pytest.mark.skipif(
    os.environ.get("GEO_TEST_ASYNC_CONTAINERS") != "1", reason="opt-in Docker lifecycle tests"
)
ROOT = Path(__file__).resolve().parents[1]
SERVICE_IDENTITY = {
    "PYGEOAPI_TITLE": "Contributor Workflow Service",
    "PYGEOAPI_DESCRIPTION": "A deployment-specific Python workflow service.",
}


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@pytest.fixture(scope="module")
def deployment(tmp_path_factory, request):
    directory = tmp_path_factory.mktemp("async-containers")
    project = "raster-async-test-" + uuid4().hex[:10]
    custom_example = getattr(request, "param", None) == "custom-process"
    example = ROOT / "examples/custom-process"
    port = free_port()
    db_port = free_port()
    environment = {
        **os.environ,
        "GEO_JOB_PASSWORD": uuid4().hex,
        "API_PORT": str(port),
        "PYGEOAPI_SERVER_URL": f"http://127.0.0.1:{port}",
        "GEO_JOB_TIMEOUT": "5",
    }
    if getattr(request, "param", None) == "service-identity":
        environment.update(SERVICE_IDENTITY)
    config = yaml.safe_load((ROOT / "config/pygeoapi.yml").read_text())
    config["resources"]["worker-probe"] = {
        "type": "process",
        "processor": {"name": "test_processes.worker_probe.WorkerProbe"},
    }
    if custom_example:
        config["resources"].update(yaml.safe_load((example / "process.yml").read_text()))
        environment["CUSTOM_PROCESS_BASE_IMAGE"] = project + ":base"
    (directory / "config.yml").write_text(yaml.safe_dump(config, allow_unicode=True))
    volumes = [
        f"{directory / 'config.yml'}:/pygeoapi/local.config.yml:ro",
        f"{ROOT / 'tests/fixtures/test_processes'}:/pygeoapi/test_processes:ro",
    ]
    override = {
        "services": {
            "api": {"image": project + ":test", "volumes": volumes},
            "worker": {"image": project + ":test", "volumes": volumes},
            "db": {"ports": [f"127.0.0.1:{db_port}:5432"]},
        }
    }
    (directory / "compose.yml").write_text(yaml.safe_dump(override))
    compose = [
        "docker",
        "compose",
        "-p",
        project,
        "-f",
        str(ROOT / "compose.release.yml"),
        *(["-f", str(example / "compose.yml")] if custom_example else []),
        "-f",
        str(directory / "compose.yml"),
    ]

    def docker(*arguments):
        result = subprocess.run(
            [*compose, *arguments], env=environment, cwd=ROOT, capture_output=True, text=True, timeout=300
        )
        with (directory / "commands.log").open("a") as stream:
            stream.write(str(arguments) + "\n" + result.stdout + result.stderr)
        result.check_returncode()
        return result.stdout

    try:
        if custom_example:
            # Build the same base/derived images as the contributor quickstart.
            build = subprocess.run(
                ["docker", "build", "-f", "docker/Dockerfile", "-t", project + ":base", "."],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=300,
            )
            (directory / "base-build.log").write_text(build.stdout + build.stderr)
            build.check_returncode()
        docker("up", "--build", "--wait", "--wait-timeout", "120")
        yield {
            "url": environment["PYGEOAPI_SERVER_URL"],
            "docker": docker,
            "dsn": f"postgresql://geo:{environment['GEO_JOB_PASSWORD']}@127.0.0.1:{db_port}/geo",
        }
    finally:
        try:
            docker("logs", "--no-color")
        finally:
            docker("down", "--volumes", "--remove-orphans")
            images = [project + ":test", *([project + ":base"] if custom_example else [])]
            subprocess.run(["docker", "image", "rm", "--no-prune", *images], check=False, capture_output=True)


def wait_ready(deployment):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        try:
            if requests.get(deployment["url"] + "/conformance", timeout=2).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.3)
    pytest.fail("API did not recover")


def submit(deployment, process="raster-info", inputs=None, **options):
    response = requests.post(
        deployment["url"] + f"/processes/{process}/execution",
        json={"inputs": inputs or {"source": DEMO_SOURCE}, **options},
        headers={"Prefer": "respond-async"},
        timeout=10,
    )
    assert response.status_code == 201, response.text
    validate_official(response.json(), "statusInfo.yaml")
    assert response.headers["Location"].startswith(deployment["url"] + "/jobs/")
    return response.headers["Location"]


def poll(url, expected=("successful", "failed")):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        response = requests.get(url, timeout=5)
        assert response.status_code == 200, response.text
        document = response.json()
        validate_official(document, "statusInfo.yaml")
        if document["status"] in expected:
            return document
        time.sleep(0.2)
    pytest.fail("Job did not reach expected status")


def test_queued_request_survives_api_and_database_restart(deployment):
    deployment["docker"]("stop", "worker")
    job = submit(deployment)
    assert requests.get(job, timeout=5).json()["status"] == "accepted"
    listed = requests.get(deployment["url"] + "/jobs", timeout=5).json()["jobs"]
    assert any(row["jobID"] == job.rsplit("/", 1)[1] and row["status"] == "accepted" for row in listed)
    pending = requests.get(job + "/results", timeout=5)
    assert pending.status_code == 404 and pending.json()["code"] == "ResultNotReady"
    deployment["docker"]("restart", "api", "db")
    wait_ready(deployment)
    assert requests.get(job, timeout=5).json()["status"] == "accepted"
    listed = requests.get(deployment["url"] + "/jobs", timeout=5).json()["jobs"]
    assert any(row["jobID"] == job.rsplit("/", 1)[1] and row["status"] == "accepted" for row in listed)
    deployment["docker"]("start", "worker")
    assert poll(job)["status"] == "successful"
    before = requests.get(job + "/results", timeout=5)
    assert before.status_code == 200 and before.json()["size"][0] > 0
    deployment["docker"]("restart", "api")
    wait_ready(deployment)
    assert requests.get(job + "/results", timeout=5).json() == before.json()
    listed = requests.get(deployment["url"] + "/jobs", timeout=5).json()["jobs"]
    assert any(row["jobID"] == job.rsplit("/", 1)[1] and row["status"] == "successful" for row in listed)


@pytest.mark.parametrize(
    "response,transmission", [("raw", "value"), ("document", "value"), ("document", "reference"), ("raw", "reference")]
)
def test_warp_results_and_downloads_survive_api_restart(deployment, response, transmission):
    job = submit(
        deployment,
        "raster-warp",
        inputs={"source": DEMO_SOURCE, "target_crs": "EPSG:4326"},
        response=response,
        outputs={"result": {"transmissionMode": transmission}},
    )
    assert poll(job)["status"] == "successful"
    deployment["docker"]("restart", "api")
    wait_ready(deployment)
    result = requests.get(job + "/results", timeout=5)
    if response == "raw" and transmission == "reference":
        assert result.status_code == 204 and not result.content and "Content-Type" not in result.headers
        href = result.headers["Link"].split("<", 1)[1].split(">", 1)[0]
        data = requests.get(href, timeout=5).content
    elif response == "document":
        assert result.status_code == 200
        if transmission == "value":
            Draft4Validator(DOCUMENT_SCHEMA, format_checker=FORMATS).validate(result.json())
            # Same known binary schema limitation as synchronous executions.
            with pytest.raises(ValidationError):
                validate_official(result.json(), "results.yaml")
        else:
            validate_official(result.json(), "results.yaml")
        value = result.json()["result"]
        data = (
            requests.get(value["href"], timeout=5).content
            if transmission == "reference"
            else base64.b64decode(value["value"])
        )
    else:
        assert result.status_code == 200 and result.headers["Content-Type"] == "image/tiff"
        data = result.content
    from rasterio.io import MemoryFile

    with MemoryFile(data) as memory, memory.open() as raster:
        assert raster.crs.to_epsg() == 4326 and raster.width > 0


def test_worker_interruption_and_timeout_are_explicit(deployment):
    job = submit(deployment, "worker-probe", inputs={"delay": 20})
    poll(job, ("running",))
    deployment["docker"]("kill", "-s", "SIGKILL", "worker")
    deployment["docker"]("start", "worker")
    assert poll(job)["status"] == "failed"
    failed = requests.get(job + "/results", timeout=5)
    assert failed.status_code == 500 and "interrupted" in failed.json()["description"]
    timeout_job = submit(deployment, "worker-probe", inputs={"delay": 20})
    assert poll(timeout_job)["status"] == "failed"
    assert requests.get(timeout_job + "/results", timeout=5).status_code == 500
    good = submit(deployment)
    assert poll(good)["status"] == "successful"


def test_worker_retains_input_security_and_sync_contract(deployment):
    bad = submit(deployment, inputs={"source": {"href": "http://127.0.0.1/private.tif", "type": "image/tiff"}})
    assert poll(bad)["status"] == "failed"
    failure = requests.get(bad + "/results", timeout=5)
    assert failure.status_code == 400 and failure.json()["code"] == "InvalidParameterValue"
    synchronous = requests.post(
        deployment["url"] + "/processes/raster-info/execution", json={"inputs": {"source": DEMO_SOURCE}}, timeout=10
    )
    assert synchronous.status_code == 200 and "Location" not in synchronous.headers
    assert requests.get(deployment["url"] + "/jobs", timeout=5).status_code == 200


@pytest.mark.parametrize("process", ["raster-sample-points", "raster-reclassify", "raster-polygonize"])
def test_other_advertised_processors_reuse_the_same_worker(deployment, process):
    from test_raster_operations import CLASSES, points, raster_source

    inputs = {"source": raster_source()}
    if process == "raster-sample-points":
        inputs["points"] = {"value": points([[4.5, 53.5]]), "mediaType": "application/geo+json"}
    elif process == "raster-reclassify":
        inputs["classes"] = CLASSES
    job = submit(
        deployment, process, inputs=inputs, response="document", outputs={"result": {"transmissionMode": "reference"}}
    )
    state = poll(job)
    assert state["status"] == "successful", requests.get(job + "/results", timeout=5).text
    result = requests.get(job + "/results", timeout=5)
    assert result.status_code == 200
    validate_official(result.json(), "results.yaml")
    downloaded = requests.get(result.json()["result"]["href"], timeout=5)
    assert downloaded.status_code == 200
    if process == "raster-reclassify":
        assert downloaded.headers["Content-Type"] == "image/tiff"
    else:
        assert downloaded.json()["type"] == "FeatureCollection"


@pytest.mark.parametrize("deployment", ["service-identity"], indirect=True)
def test_release_service_metadata_overrides_preserve_execution(deployment):
    base = deployment["url"]
    landing = requests.get(base + "/?f=json", timeout=5).json()
    definition = requests.get(base + "/openapi?f=json", timeout=5).json()
    assert landing["title"] == definition["info"]["title"] == SERVICE_IDENTITY["PYGEOAPI_TITLE"]
    assert landing["description"] == definition["info"]["description"] == SERVICE_IDENTITY["PYGEOAPI_DESCRIPTION"]
    code = """
import json, os
from pygeoapi.util import yaml_load
with open(os.environ['PYGEOAPI_CONFIG']) as stream:
    print(json.dumps(yaml_load(stream)['metadata']['identification']))
"""
    worker_identity = json.loads(deployment["docker"]("exec", "-T", "worker", "/venv/bin/python3", "-c", code))
    assert worker_identity["title"] == SERVICE_IDENTITY["PYGEOAPI_TITLE"]
    assert worker_identity["description"] == SERVICE_IDENTITY["PYGEOAPI_DESCRIPTION"]
    notice = deployment["docker"]("exec", "-T", "api", "cat", "/licenses/python-ogc-processes/LICENSE")
    assert notice == (ROOT / "LICENSE").read_text()
    synchronous = requests.post(
        base + "/processes/raster-info/execution", json={"inputs": {"source": DEMO_SOURCE}}, timeout=10
    )
    assert synchronous.status_code == 200
    job = submit(deployment)
    assert poll(job)["status"] == "successful"
    asynchronous = requests.get(job + "/results", timeout=5)
    assert asynchronous.status_code == 200 and asynchronous.json() == synchronous.json()


@pytest.mark.parametrize("deployment", ["custom-process"], indirect=True)
@pytest.mark.parametrize("response", ["raw", "document"])
def test_custom_process_example_uses_api_and_worker(deployment, response):
    base = deployment["url"]
    description = requests.get(base + "/processes/text-statistics?f=json", timeout=5)
    assert description.status_code == 200
    validate_official(description.json(), "process.yaml")
    assert description.json()["jobControlOptions"] == ["sync-execute", "async-execute"]
    listing = requests.get(base + "/processes?f=json", timeout=5).json()
    assert "text-statistics" in {item["id"] for item in listing["processes"]}
    specification = requests.get(base + "/openapi?f=json", timeout=5).json()
    operation = specification["paths"]["/processes/text-statistics/execution"]["post"]
    assert {"200", "201", "400", "503"} <= set(operation["responses"])
    inputs = {"text": "Bring your own Python!"}
    document = {"inputs": inputs, "response": response}
    synchronous = requests.post(base + "/processes/text-statistics/execution", json=document, timeout=10)
    assert synchronous.status_code == 200 and "Location" not in synchronous.headers
    expected = {"characters": 22, "words": 4}
    if response == "document":
        expected = {"statistics": {"value": expected}}
        validate_official(synchronous.json(), "results.yaml")
    assert synchronous.json() == expected
    job = submit(deployment, "text-statistics", inputs=inputs, response=response)
    assert poll(job)["status"] == "successful"
    asynchronous = requests.get(job + "/results", timeout=5)
    assert asynchronous.status_code == 200
    assert asynchronous.headers["Content-Type"] == synchronous.headers["Content-Type"]
    assert asynchronous.json() == synchronous.json()
    Draft4Validator(operation["responses"]["200"]["content"]["application/json"]["schema"]).validate(expected)


@pytest.mark.parametrize("deployment", ["custom-process"], indirect=True)
def test_custom_process_errors_use_existing_http_and_job_contracts(deployment):
    inputs = {"text": 42}
    synchronous = requests.post(
        deployment["url"] + "/processes/text-statistics/execution", json={"inputs": inputs}, timeout=10
    )
    assert synchronous.status_code == 400 and synchronous.json()["code"] == "InvalidParameterValue"
    validate_official(synchronous.json(), "exception.yaml")
    job = submit(deployment, "text-statistics", inputs=inputs)
    assert poll(job)["status"] == "failed"
    asynchronous = requests.get(job + "/results", timeout=5)
    assert asynchronous.status_code == 400
    assert asynchronous.json() == synchronous.json()


@pytest.mark.parametrize("deployment", [None, "custom-process"], indirect=True)
def test_api_and_worker_dependencies_match_the_production_lock(deployment):
    requirements = subprocess.run(
        ["uv", "export", "--locked", "--no-dev", "--no-emit-project", "--no-hashes", "--no-header", "--no-annotate"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout
    # Evaluate platform markers in the container, not on a potentially different host OS.
    script = """
import json, sys
from importlib.metadata import version
from packaging.requirements import Requirement
import pygeoapi
requirements = [Requirement(line) for line in sys.argv[1].splitlines() if line.strip()]
selected = [item for item in requirements if item.marker is None or item.marker.evaluate()]
versions = {item.name: version(item.name) for item in selected}
for item in selected:
    assert item.specifier.contains(versions[item.name]), (str(item), versions[item.name])
assert pygeoapi.__version__ == versions['pygeoapi']
assert version('gunicorn')
print(json.dumps(versions, sort_keys=True))
"""
    versions = [
        json.loads(deployment["docker"]("exec", "-T", service, "/venv/bin/python3", "-c", script, requirements))
        for service in ("api", "worker")
    ]
    assert versions[0] == versions[1]
    images = deployment["docker"]("images", "--quiet", "api", "worker").splitlines()
    assert images and len(set(images)) == 1


def test_image_build_rejects_an_outdated_lockfile(tmp_path):
    # Keep the repository and its lock untouched; build only this disposable context.
    for directory in ("docker", "src", "config"):
        shutil.copytree(ROOT / directory, tmp_path / directory, ignore=shutil.ignore_patterns("__pycache__"))
    for filename in ("pyproject.toml", "uv.lock", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / filename, tmp_path / filename)
    manifest = tmp_path / "pyproject.toml"
    # This package is already transitively locked: only the root declaration becomes stale.
    manifest.write_text(manifest.read_text().replace("dependencies = [", 'dependencies = [\n    "requests",', 1))
    original_lock = (tmp_path / "uv.lock").read_bytes()
    result = subprocess.run(
        ["docker", "build", "-f", "docker/Dockerfile", "."],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=300,
    )
    (tmp_path / "stale-build.log").write_text(result.stdout + result.stderr)
    assert result.returncode != 0
    assert "needs to be updated" in result.stderr and "--locked" in result.stderr
    assert (tmp_path / "uv.lock").read_bytes() == original_lock
