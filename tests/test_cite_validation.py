"""Test validation orchestration/report semantics, not the external algorithms."""

import json
from zipfile import ZipFile

import pytest
import yaml

from scripts import validate_cite as cite


def test_cite_config_uses_combined_manager_and_retains_real_processes(tmp_path, service_config):
    config = cite.prepare_config(tmp_path / "config.yml")
    assert config["server"]["manager"]["name"] == "geo_processes.async_manager.DurableProcessManager"
    assert config["server"]["manager"]["connection"].startswith("postgresql://geo:")
    assert set(config["resources"]) == set(service_config["resources"]) | {"cite-echo"}
    for name, resource in service_config["resources"].items():
        if resource["type"] == "process":
            assert config["resources"][name] == resource
    assert config["server"]["url"] == "http://api:8080"
    assert "cite-echo" not in service_config["resources"]


def test_cite_cli_includes_the_engine_html_resources_on_its_classpath():
    config = yaml.safe_load((cite.ROOT / "compose.cite.yml").read_text())
    entrypoint = config["services"]["cite"]["entrypoint"]
    classpath = entrypoint[entrypoint.index("-cp") + 1].split(":")
    assert "/usr/local/tomcat/webapps/teamengine/WEB-INF/classes" in classpath


@pytest.mark.parametrize("mode", ["raw", "document"])
def test_cite_echo_http_response_contains_the_original_message(http_client, monkeypatch, mode):
    from pygeoapi.flask_app import api_

    monkeypatch.setitem(api_.manager.processes, "cite-echo", {"processor": {"name": cite.CLASS_NAME}})
    message = 'Café "quoted" text\nwith a backslash: \\'
    response = http_client.post(
        "/processes/cite-echo/execution", json={"inputs": {"message": message}, "response": mode}
    )
    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert response.json == (message if mode == "raw" else {"message": {"value": message}})
    invalid = http_client.post("/processes/cite-echo/execution", json={"inputs": {"message": 12}, "response": mode})
    assert invalid.status_code == 400 and invalid.json["code"] == "InvalidParameterValue"


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


def test_official_reports_are_retained_and_linked_from_summaries(tmp_path):
    run = tmp_path / "reports/testng/run-id"
    (run / "result").mkdir(parents=True)
    (run / "result/index.html").write_text('<html><script src="js/report.js"></script></html>')
    (run / "result/js").mkdir()
    (run / "result/js/report.js").write_text("// official report asset")
    with ZipFile(run / "result.zip", "w") as archive:
        archive.write(run / "result/index.html", "index.html")
    metadata = cite.official_reports(tmp_path, report(run))
    assert metadata == {
        "officialHtmlReport": "reports/testng/run-id/result/index.html",
        "nativeHtmlArchive": "reports/testng/run-id/result.zip",
        "officialHtmlArchive": "official-report.zip",
    }
    with ZipFile(tmp_path / metadata["officialHtmlArchive"]) as archive:
        assert archive.read("index.html") == (run / "result/index.html").read_bytes()
        assert archive.read("js/report.js") == (run / "result/js/report.js").read_bytes()
    with ZipFile(tmp_path / metadata["nativeHtmlArchive"]) as archive:
        assert archive.namelist() == ["index.html"]  # original engine ZIP is unchanged
    cite.write_reports(tmp_path, cite.summarize(run / "testng-results.xml"), metadata)
    assert f'href="{metadata["officialHtmlReport"]}"' in (tmp_path / "summary.html").read_text()
    assert f"({metadata['officialHtmlArchive']})" in (tmp_path / "summary.md").read_text()


@pytest.mark.parametrize("artifact", ["index.html", "result.zip", "invalid-zip"])
def test_missing_or_invalid_official_report_is_an_infrastructure_error(tmp_path, artifact):
    (tmp_path / "result").mkdir()
    (tmp_path / "result/index.html").write_text("official report")
    with ZipFile(tmp_path / "result.zip", "w") as archive:
        archive.writestr("index.html", "official report")
    if artifact == "invalid-zip":
        (tmp_path / "result.zip").write_text("not a ZIP")
    else:
        (tmp_path / ("result/index.html" if artifact == "index.html" else "result.zip")).unlink()
    with pytest.raises(cite.InfrastructureError, match="official TEAM Engine|Official TEAM Engine"):
        cite.official_reports(tmp_path, tmp_path / "testng-results.xml")


def test_cleanup_is_scoped_and_still_runs_when_log_collection_fails(tmp_path, monkeypatch):
    (tmp_path / "compose.cite.yml").write_text("test profile")
    (tmp_path / "compose.base.yml").write_text("shared combined deployment")
    monkeypatch.setattr(cite, "ROOT", tmp_path)
    monkeypatch.setattr(cite, "source_fingerprint", lambda: "fingerprint")

    def config(path, **_kwargs):
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
    properties = next(tmp_path.glob("runtime-data/cite/*/test-run-props.xml")).read_text()
    assert '<entry key="acceptMediaType">application/zip</entry>' in properties
    assert any("down" in command for command in commands)
    teardown = next(command for command in commands if "down" in command)
    assert teardown[teardown.index("--profile") + 1] == "browser"
    assert any(command[:3] == ["docker", "image", "rm"] for command in commands)
    projects = [command[command.index("--project-name") + 1] for command in commands if "--project-name" in command]
    assert projects and len(set(projects)) == 1 and projects[0].startswith("raster-cite-")


def test_geonovum_config_has_only_real_processes_and_host_reachable_urls(tmp_path, service_config, monkeypatch):
    monkeypatch.setenv("GEO_MANAGER_CLASS", "geo_processes.manager.OgcSynchronousManager")
    config = cite.prepare_config(tmp_path / "config.yml", echo=False, public_url="http://127.0.0.1:59999")
    assert set(config["resources"]) == set(service_config["resources"])
    assert config["server"]["manager"]["name"] == "geo_processes.async_manager.DurableProcessManager"
    assert config["server"]["url"] == "http://127.0.0.1:59999"
    assert config["server"]["logo"].startswith("http://127.0.0.1:59999/")
    assert all(
        link["href"].startswith("http://127.0.0.1:59999/") for link in config["resources"]["sample-points"]["links"]
    )
