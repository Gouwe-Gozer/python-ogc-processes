"""Test validation orchestration/report semantics, not the external algorithms."""

import json

import pytest
import yaml

from geo_processes.manager import InvalidExecutionRequestError, OgcSynchronousManager
from scripts import validate_cite as cite


def test_cite_config_retains_real_processes_manager_and_adds_only_sync_fixture(tmp_path, service_config):
    config = cite.prepare_config(tmp_path / "config.yml")
    assert config["server"]["manager"] == service_config["server"]["manager"]
    assert set(config["resources"]) == set(service_config["resources"]) | {"cite-echo"}
    for name, resource in service_config["resources"].items():
        if resource["type"] == "process":
            assert config["resources"][name] == resource
    assert config["server"]["url"] == "http://api:8080"
    assert "cite-echo" not in service_config["resources"]


@pytest.mark.parametrize("mode", ["raw", "document"])
def test_cite_echo_executes_through_the_real_synchronous_manager(mode):
    manager = OgcSynchronousManager(
        {"name": "test", "processes": {"cite-echo": {"processor": {"name": cite.CLASS_NAME}}}}
    )
    processor = manager.get_processor("cite-echo")
    assert processor.metadata["jobControlOptions"] == ["sync-execute"]
    _, media, result, status, _ = manager.execute_process("cite-echo", {"message": "hello"}, requested_response=mode)
    assert media == "application/json" and status.value == "successful"
    assert (json.loads(result) if mode == "raw" else result) == (
        "hello" if mode == "raw" else {"message": {"value": "hello"}}
    )
    with pytest.raises(InvalidExecutionRequestError):
        manager.execute_process("cite-echo", {"message": 12})


def report(tmp_path, *, fail="bad <input>", passed=1):
    path = tmp_path / "testng-results.xml"
    path.write_text(f'''<testng-results passed="{passed}" failed="1" skipped="1">
    <suite name="suite-1"><test name="Core"><class name="Tests">
    <test-method name="setup" status="PASS" is-config="true"/>
    <test-method name="good" status="PASS"/>
    <test-method name="bad" status="FAIL" description="Requirement /req/core/example">
    <exception><message><![CDATA[{fail}]]></message></exception></test-method>
    <test-method name="conditional" status="SKIP"><exception><message>unsupported</message></exception></test-method>
    </class></test></suite></testng-results>''')
    return path


def test_native_failures_and_skips_are_preserved_in_machine_and_human_reports(tmp_path):
    summary = cite.summarize(report(tmp_path))
    assert summary["counts"] == {"PASS": 1, "FAIL": 1, "SKIP": 1}
    assert len(summary["cases"]) == 3 and not summary["configurationFailures"]
    cite.write_reports(tmp_path, summary, {"image": "pinned"})
    assert json.loads((tmp_path / "summary.json").read_text()) == summary
    html = (tmp_path / "summary.html").read_text()
    assert "bad &lt;input&gt;" in html and "bad <input>" not in html


def test_inconsistent_or_missing_results_are_not_treated_as_conformance_success(tmp_path):
    with pytest.raises(cite.InfrastructureError, match="total"):
        cite.summarize(report(tmp_path, passed=2))
    with pytest.raises(cite.InfrastructureError, match="Unreadable"):
        cite.summarize(tmp_path / "missing.xml")


def test_cleanup_is_scoped_and_still_runs_when_log_collection_fails(tmp_path, monkeypatch):
    (tmp_path / "compose.cite.yml").write_text("test profile")
    monkeypatch.setattr(cite, "ROOT", tmp_path)
    monkeypatch.setattr(cite, "source_fingerprint", lambda: "fingerprint")

    def config(path):
        data = {"server": {"manager": {"name": "real-manager"}}, "resources": {}}
        path.write_text(yaml.safe_dump(data))
        return data

    monkeypatch.setattr(cite, "prepare_config", config)
    commands = []

    def command(arguments, **kwargs):
        commands.append(arguments)
        if "up" in arguments or "logs" in arguments:
            raise cite.InfrastructureError("simulated infrastructure failure")
        return "commit" if arguments[:2] == ["git", "rev-parse"] else ""

    monkeypatch.setattr(cite, "command", command)
    assert cite.run() == 2
    assert any("down" in command for command in commands)
    teardown = next(command for command in commands if "down" in command)
    assert teardown[teardown.index("--profile") + 1] == "browser"
    assert any(command[:3] == ["docker", "image", "rm"] for command in commands)
    projects = [command[command.index("--project-name") + 1] for command in commands if "--project-name" in command]
    assert projects and len(set(projects)) == 1 and projects[0].startswith("raster-cite-")
