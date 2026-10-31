"""The explicit opt-out starts only the API and requires no job database."""

import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
import requests
import yaml
from raster_fixtures import DEMO_SOURCE

pytestmark = pytest.mark.skipif(
    os.environ.get("GEO_TEST_ASYNC_CONTAINERS") != "1", reason="opt-in Docker deployment test"
)
ROOT = Path(__file__).resolve().parents[1]


def test_lightweight_optout_starts_without_database_or_worker(tmp_path):
    project = "raster-async-test-sync-" + uuid4().hex[:10]
    override = {"services": {"api": {"image": project + ":test", "ports": ["127.0.0.1::8080"]}}}
    # API_PORT=0 also makes the inherited host-port mapping ephemeral.
    environment = {**os.environ, "API_PORT": "0"}
    (tmp_path / "compose.yml").write_text(yaml.safe_dump(override).replace("    ports:\n", "    ports: !override\n"))
    compose = [
        "docker",
        "compose",
        "-p",
        project,
        "-f",
        str(ROOT / "compose.release.yml"),
        "-f",
        str(ROOT / "compose.sync.yml"),
        "-f",
        str(tmp_path / "compose.yml"),
    ]

    def docker(*arguments):
        result = subprocess.run(
            [*compose, *arguments], env=environment, cwd=ROOT, text=True, capture_output=True, timeout=300
        )
        with (tmp_path / "commands.log").open("a") as stream:
            stream.write(str(arguments) + "\n" + result.stdout + result.stderr)
        result.check_returncode()
        return result.stdout.strip()

    try:
        docker("up", "--build", "--wait", "--wait-timeout", "120")
        assert docker("ps", "--services", "--status", "running") == "api"
        port = docker("port", "api", "8080").splitlines()[0]
        url = "http://" + port
        description = requests.get(url + "/processes/raster-info?f=json", timeout=5).json()
        assert description["jobControlOptions"] == ["sync-execute"]
        response = requests.post(
            url + "/processes/raster-info/execution",
            json={"inputs": {"source": DEMO_SOURCE}},
            headers={"Prefer": "respond-async"},
            timeout=10,
        )
        assert response.status_code == 200 and "Location" not in response.headers
    finally:
        try:
            docker("logs", "--no-color")
        finally:
            docker("down", "--volumes", "--remove-orphans")
            subprocess.run(["docker", "image", "rm", "--no-prune", project + ":test"], capture_output=True, check=False)
