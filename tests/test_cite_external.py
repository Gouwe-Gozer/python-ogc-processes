"""External validation must preserve results and only manage its own validator."""

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from scripts import validate_cite_external as cite


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/api",
        "example.org",
        "https://u:p@example.org",
        "https://example.org?token=abc",
        "https://example.org/#x",
        "http://example.org:bad",
        "http://example.org/a\nb",
    ],
)
def test_invalid_or_credential_bearing_target_is_rejected(url):
    with pytest.raises(argparse.ArgumentTypeError):
        cite.base_url(url)


def test_cli_preserves_api_prefix_and_requires_explicit_echo_process():
    args = cite.parse_args(["--base-url", "https://example.org/ogc/api/", "--echo-process", "echo"])
    assert args.base_url == "https://example.org/ogc/api"
    assert args.echo_process == "echo" and args.timeout == 900
    with pytest.raises(SystemExit):
        cite.parse_args(["--base-url", "https://example.org"])
    with pytest.raises(SystemExit):
        cite.parse_args(["--base-url", "https://example.org", "--echo-process", "echo", "--timeout", "0"])


def native_reports(directory, *, failed=0, skipped=0, configuration_failure=False):
    native = directory / "reports/testng/run-id"
    result = native / "result"
    (result / "styles").mkdir(parents=True)
    (result / "index.html").write_text('<link rel="stylesheet" href="styles/report.css">official HTML')
    (result / "styles/report.css").write_text("body { color: black; }")
    (native / "earl-results.rdf").write_text("<rdf/>")
    with ZipFile(native / "result.zip", "w") as archive:
        archive.write(result / "index.html", "index.html")
    root = ET.Element("testng-results", passed="1", failed=str(failed), skipped=str(skipped))
    group = ET.SubElement(ET.SubElement(root, "suite", name=cite.SUITE), "test", name="Core")
    tests = ET.SubElement(group, "class", name="OfficialTests")
    ET.SubElement(tests, "test-method", name="good", status="PASS")
    for number in range(failed):
        method = ET.SubElement(tests, "test-method", name=f"bad-{number}", status="FAIL")
        ET.SubElement(ET.SubElement(method, "exception"), "message").text = "real failure"
    for number in range(skipped):
        ET.SubElement(tests, "test-method", name=f"optional-{number}", status="SKIP")
    if configuration_failure:
        ET.SubElement(tests, "test-method", name="setup", status="FAIL", attrib={"is-config": "true"})
    ET.ElementTree(root).write(native / "testng-results.xml")
    return native


@pytest.mark.parametrize("failure", ["missing", "counts", "all-skipped", "suite"])
def test_absent_or_inconsistent_reports_cannot_produce_a_pass(tmp_path, failure):
    native = native_reports(tmp_path)
    path = native / "testng-results.xml"
    if failure == "missing":
        path.unlink()
    else:
        tree = ET.parse(path)
        root = tree.getroot()
        if failure == "counts":
            root.set("passed", "9")
        elif failure == "all-skipped":
            root.set("passed", "0")
            root.set("skipped", "1")
            root.find(".//test-method").set("status", "SKIP")
        else:
            root.find("suite").set("name", "another-suite")
        tree.write(path)
    with pytest.raises((cite.InfrastructureError, OSError)):
        cite.collect_reports(tmp_path)


def test_report_bundle_preserves_official_bytes_paths_and_native_zip(tmp_path):
    native = native_reports(tmp_path, failed=1, skipped=1)
    original_zip = (native / "result.zip").read_bytes()
    summary, artifacts = cite.collect_reports(tmp_path)
    assert summary["counts"] == {"PASS": 1, "FAIL": 1, "SKIP": 1}
    assert (native / "result.zip").read_bytes() == original_zip
    with ZipFile(tmp_path / artifacts["officialHtmlArchive"]) as archive:
        for name in ("index.html", "styles/report.css"):
            assert archive.read(name) == (native / "result" / name).read_bytes()
    assert json.loads((tmp_path / "summary.json").read_text()) == summary


@pytest.mark.parametrize(
    "scenario, expected",
    [
        ("pass", 0),
        ("fail", 1),
        ("setup-fail", 1),
        ("timeout", 2),
        ("missing-report", 2),
        ("cleanup-fail", 2),
        ("interrupt", 130),
    ],
)
def test_external_run_only_manages_its_validator_and_retains_real_status(tmp_path, monkeypatch, scenario, expected):
    args = cite.parse_args(
        [
            "--base-url",
            "http://external-api:8080/prefix",
            "--echo-process",
            "echo<&>",
            "--output-dir",
            str(tmp_path),
            "--network",
            "existing-network",
            "--timeout",
            "60",
        ]
    )
    calls = []

    def command(arguments, *, log, timeout):
        calls.append(arguments)
        log.write_text("validator log")
        if arguments[:2] == ["docker", "start"]:
            assert timeout == 60
            if scenario == "timeout":
                raise cite.InfrastructureError("timed out")
            if scenario == "interrupt":
                raise KeyboardInterrupt
            if scenario != "missing-report":
                native_reports(
                    log.parent, failed=int(scenario == "fail"), configuration_failure=scenario == "setup-fail"
                )
        if arguments[:2] == ["docker", "rm"] and scenario == "cleanup-fail":
            raise cite.InfrastructureError("cleanup failed")

    monkeypatch.setattr(cite, "command", command)
    assert cite.run(args) == expected
    assert [call[:2] for call in calls] == [["docker", "create"], ["docker", "start"], ["docker", "rm"]]
    create = calls[0]
    assert create[create.index("--network") + 1] == "existing-network"
    assert cite.IMAGE in create and cite.CONTROLLER in create and cite.CLASSPATH in create
    assert calls[1][-1] == calls[2][-1] == create[create.index("--name") + 1]
    directory = next(tmp_path.iterdir())
    properties = {node.get("key"): node.text for node in ET.parse(directory / "test-run-props.xml").getroot()}
    assert properties["iut"] == args.base_url
    assert properties["echoprocessid"] == "echo<&>"
    assert properties["acceptMediaType"] == "application/zip"
    assert json.loads((directory / "metadata.json").read_text())["exitCode"] == expected


def test_script_is_standalone_and_never_imports_our_application():
    # Imports are stdlib-only so copying just this file to another project works.
    import ast
    import sys

    tree = ast.parse(Path(cite.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module]
        else:
            continue
        assert all(name.split(".")[0] in sys.stdlib_module_names or name == "__future__" for name in names)
