"""Deterministic tests for the Geonovum diagnostic baseline runner."""

import json
import subprocess

import pytest

import scripts.check_geonovum_baseline as geonovum


def diagnostic(code, path, message="message", severity="error"):
    return {
        "severity": severity,
        "message": message,
        "code": code,
        "path": path,
        "documentationUrl": f"https://example.test/{code}",
        "source": "https://example.test/ruleset",
    }


def report(*diagnostics):
    return {
        "valid": not diagnostics,
        "diagnostics": list(diagnostics),
        "rulesets": ["https://example.test/ruleset"],
    }


def test_normalize_report_sorts_and_records_pinned_versions():
    normalized = geonovum.normalize_report(
        report(
            diagnostic("second", ["paths", "second"]),
            diagnostic("first", ["paths", "first"]),
        )
    )

    assert normalized["checker"] == {
        "package": "@geonovum/ogc-checker",
        "version": "1.2.0",
    }
    assert normalized["standard"] == {
        "id": "ogc-api-processes",
        "version": "1.0.0",
    }
    assert [item["code"] for item in normalized["diagnostics"]] == ["first", "second"]


def test_transient_detection_does_not_hide_stable_invalid_references():
    network_failure = diagnostic("invalid-ref", ["components"], "FetchError: socket hang up")
    actual_invalid_reference = diagnostic("invalid-ref", ["components"], "JSON pointer does not exist")
    schema_timeout = diagnostic(
        "/req/core/example",
        ["paths"],
        "Could not load reference schema: Timed out resolving $refs after 5000ms",
    )

    assert geonovum.transient_diagnostics(report(network_failure, actual_invalid_reference, schema_timeout)) == [
        network_failure,
        schema_timeout,
    ]


def test_comparison_reports_added_removed_and_changed_diagnostics():
    unchanged = diagnostic("unchanged", ["paths", "same"])
    old_changed = diagnostic("changed", ["paths", "changed"], message="old")
    new_changed = diagnostic("changed", ["paths", "changed"], message="new")
    removed = diagnostic("removed", ["paths", "removed"])
    added = diagnostic("added", ["paths", "added"])

    baseline = geonovum.normalize_report(report(unchanged, old_changed, removed))
    current = geonovum.normalize_report(report(unchanged, new_changed, added))

    additions, removals, changes, metadata_changes = geonovum.compare_reports(baseline, current)

    assert additions == [added]
    assert removals == [removed]
    assert changes == [(old_changed, new_changed)]
    assert metadata_changes == []


def test_checker_retries_network_failure_and_returns_complete_report(monkeypatch):
    transient = report(diagnostic("invalid-ref", ["paths"], "FetchError: socket hang up"))
    complete = report(diagnostic("/req/core/example", ["paths"]))
    results = iter(
        [
            subprocess.CompletedProcess([], 0, json.dumps(transient), ""),
            subprocess.CompletedProcess([], 0, json.dumps(complete), ""),
        ]
    )
    waits = []
    commands = []

    def run(command, **_kwargs):
        commands.append(command)
        return next(results)

    monkeypatch.setattr(geonovum.shutil, "which", lambda _command: "/usr/bin/npx")

    normalized = geonovum.run_checker(
        "http://127.0.0.1:5001/openapi?f=json",
        attempts=2,
        command_runner=run,
        wait=waits.append,
    )

    assert len(commands) == 2
    assert waits == [2]
    assert "@geonovum/ogc-checker@1.2.0" in commands[0]
    assert commands[0][commands[0].index("--version") + 1] == "1.0.0"
    assert [item["code"] for item in normalized["diagnostics"]] == ["/req/core/example"]


def test_checker_rejects_duplicate_diagnostic_identities():
    duplicate = diagnostic("same", ["paths"])

    with pytest.raises(geonovum.CheckerOperationalError, match="duplicate"):
        geonovum.normalize_report(report(duplicate, duplicate))


def test_input_source_normalization_preserves_diagnostics_across_ports():
    first = diagnostic("rule", ["paths"])
    second = {**first, "source": "http://127.0.0.1:5002/openapi?f=json"}
    first["source"] = "http://127.0.0.1:5001/openapi?f=json"
    left = geonovum.normalize_report(report(first), first["source"])
    right = geonovum.normalize_report(report(second), second["source"])
    assert left == right
    assert left["diagnostics"][0] == {**first, "source": "<input>"}
    unchanged = geonovum.normalize_report(report(first), "http://different.test/openapi")
    assert unchanged["diagnostics"][0]["source"] == first["source"]


def test_source_only_mismatch_is_visible_and_does_not_pass_comparison():
    original = diagnostic("rule", ["paths"])
    changed = {**original, "source": "https://different.test/schema.yaml"}
    baseline = geonovum.normalize_report(report(original))
    current = geonovum.normalize_report(report(changed))
    added, removed, changes, metadata_changes = geonovum.compare_reports(baseline, current)
    assert added == [changed] and removed == [original]
    assert not changes and not metadata_changes
    assert original["source"] in geonovum.describe_diagnostic(removed[0])
    assert changed["source"] in geonovum.describe_diagnostic(added[0])


def test_run_checker_normalizes_its_input_source_before_baseline_comparison(monkeypatch):
    input_url = "http://127.0.0.1:5001/openapi?f=json"
    raw = report({**diagnostic("rule", ["paths"]), "source": input_url})
    expected = geonovum.normalize_report(report({**raw["diagnostics"][0], "source": "<input>"}))
    monkeypatch.setattr(geonovum.shutil, "which", lambda _command: "/usr/bin/npx")
    current = geonovum.run_checker(
        input_url,
        attempts=1,
        command_runner=lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, json.dumps(raw), ""),
    )
    assert not any(geonovum.compare_reports(expected, current))
