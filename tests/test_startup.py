"""Fail before serving requests when effective deployment settings are invalid."""

import os
import subprocess
import sys

import pytest
import yaml

from geo_processes.startup import ConfigurationError, public_url, validate_runtime


@pytest.fixture()
def runtime_environment(monkeypatch, tmp_path):
    for name in os.environ:
        if name.startswith(("GEO_", "WSGI_")) or name == "CONTAINER_PORT":
            monkeypatch.delenv(name)
    monkeypatch.setenv("GEO_INPUT_TMPDIR", str(tmp_path / "inputs"))
    monkeypatch.setenv("GEO_OUTPUT_DIR", str(tmp_path / "results"))
    return tmp_path


@pytest.mark.parametrize(
    "url",
    [
        "",
        "/relative",
        "ftp://example.test",
        "https://user:secret@example.test",
        "https://example.test?secret=1",
        "https://example.test#fragment",
        "http://example.test:invalid",
        "http://example.test:0",
        "https://example.test/white space",
        "https://example.test/\npath",
        "http://[broken",
        "http://example.test\\x",
    ],
)
def test_bad_public_url_is_rejected_without_echoing_credentials(url):
    with pytest.raises(ConfigurationError, match="PYGEOAPI_SERVER_URL") as error:
        public_url(url)
    assert "secret" not in str(error.value)


def test_effective_settings_and_probes_preserve_results(service_config, runtime_environment, monkeypatch):
    root = runtime_environment
    (root / "results").mkdir()
    retained = root / "results" / "0123456789abcdef0123456789abcdef.tif"
    retained.write_bytes(b"retained result")
    monkeypatch.setenv("GEO_INPUT_ALLOWED_HOSTS", "DATA.example.org., assets.example.org")
    monkeypatch.setenv("GEO_RESULT_RETENTION_SECONDS", "3600")
    monkeypatch.setenv("WSGI_WORKERS", "3")
    settings = validate_runtime({**service_config, "server": {"url": "https://example.test/geo/"}})
    summary = settings.summary()
    assert settings.url == "https://example.test/geo"
    assert "raster-info, raster-warp" in summary
    assert "assets.example.org, data.example.org" in summary
    assert "retention 3600s" in summary and "3 sync workers" in summary
    assert "16777216 bytes" in summary and "1048576 samples" in summary
    assert retained.read_bytes() == b"retained result"
    assert list((root / "inputs").iterdir()) == []
    assert list((root / "results").iterdir()) == [retained]


@pytest.mark.parametrize(
    "name,value,match",
    [
        ("GEO_RESULT_MAX_COUNT", "hello", "GEO_RESULT_MAX_COUNT"),
        ("GEO_RESULT_MAX_BYTES", "0", "GEO_RESULT_MAX_BYTES"),
        ("GEO_RESULT_RETENTION_SECONDS", "604801", "retention"),
        ("GEO_RESULT_MAX_COUNT", "10001", "result count"),
        ("GEO_RESULT_MAX_BYTES", "1073741825", "result capacity"),
        ("GEO_INPUT_TMPDIR", " ", "GEO_INPUT_TMPDIR"),
        ("GEO_OUTPUT_DIR", "", "GEO_OUTPUT_DIR"),
        ("CONTAINER_PORT", "65536", "CONTAINER_PORT"),
        ("WSGI_WORKERS", "0", "WSGI_WORKERS"),
        ("WSGI_WORKER_TIMEOUT", "not-an-int", "WSGI_WORKER_TIMEOUT"),
        ("GEO_INPUT_ALLOWED_HOSTS", "https://example.org", "GEO_INPUT_ALLOWED_HOSTS"),
        ("GEO_INPUT_ALLOWED_HOSTS", "*.example.org", "GEO_INPUT_ALLOWED_HOSTS"),
        ("GEO_INPUT_ALLOWED_HOSTS", "example.org,", "GEO_INPUT_ALLOWED_HOSTS"),
    ],
)
def test_invalid_settings_fail_before_creating_storage(
    service_config, runtime_environment, monkeypatch, name, value, match
):
    monkeypatch.setenv(name, value)
    with pytest.raises(ConfigurationError, match=match):
        validate_runtime(service_config)
    assert list(runtime_environment.iterdir()) == []


@pytest.mark.parametrize("suffix", ["", "/nested"])
def test_input_and_output_directories_cannot_overlap(service_config, runtime_environment, monkeypatch, suffix):
    monkeypatch.setenv("GEO_INPUT_TMPDIR", str(runtime_environment / "results") + suffix)
    with pytest.raises(ConfigurationError, match="non-nested"):
        validate_runtime(service_config)


def test_non_directory_storage_is_reported(service_config, runtime_environment):
    (runtime_environment / "results").write_text("a file, not a directory")
    with pytest.raises(ConfigurationError, match="GEO_OUTPUT_DIR must be a writable directory"):
        validate_runtime(service_config)


def test_preflight_command_succeeds_or_exits_with_clear_error(service_config, runtime_environment, monkeypatch):
    config_path = runtime_environment / "config.yml"
    config_path.write_text(yaml.safe_dump(service_config))
    command = [sys.executable, "-m", "geo_processes.startup", "--config", str(config_path)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0 and "Public URL: http://example.test" in result.stdout
    monkeypatch.setenv("GEO_RESULT_RETENTION_SECONDS", "invalid")
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "Startup configuration error: GEO_RESULT_RETENTION_SECONDS" in result.stderr
    assert "Traceback" not in result.stderr
