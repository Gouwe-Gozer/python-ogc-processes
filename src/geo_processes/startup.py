"""Validate effective service settings before accepting requests."""

import argparse
import ipaddress
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from pygeoapi.util import yaml_load

from geo_processes import engine
from geo_processes.inputs import INPUT_SLOTS, MAX_EXECUTION_BYTES
from geo_processes.storage import ResultStore


class ConfigurationError(ValueError):
    """An operator setting prevents the service from starting."""


def public_url(value):
    """Check a canonical HTTP(S) base URL, including optional proxy prefix."""
    try:
        if not isinstance(value, str) or not value or any(ord(char) <= 32 or ord(char) >= 127 for char in value):
            raise ValueError
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or "?" in value
            or "#" in value
            or "\\" in value
            or "%" in parsed.hostname
            or (parsed.port is not None and not 1 <= parsed.port <= 65535)
        ):
            raise ValueError
    except ValueError as error:
        raise ConfigurationError(
            "server.url / PYGEOAPI_SERVER_URL must be an absolute HTTP(S) URL without credentials, "
            "query, fragment or whitespace"
        ) from error
    return value.rstrip("/")


def _allowed_hosts():
    value = os.environ.get("GEO_INPUT_ALLOWED_HOSTS", "")
    if not value.strip():
        return ()
    hosts = tuple(sorted({item.strip().lower().rstrip(".") for item in value.split(",")}))
    for host in hosts:
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if (
                not host
                or len(host) > 253
                or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split("."))
            ):
                raise ConfigurationError(
                    "GEO_INPUT_ALLOWED_HOSTS must contain comma-separated exact ASCII hostnames or IP addresses; "
                    "URLs, wildcards and empty entries are unsupported"
                ) from None
    return hosts


def _positive_integer(name, default, maximum=None):
    try:
        value = int(os.environ.get(name, str(default)))
        if value < 1 or (maximum is not None and value > maximum):
            raise ValueError
    except ValueError as error:
        bound = f" between 1 and {maximum}" if maximum is not None else " greater than zero"
        raise ConfigurationError(f"{name} must be an integer{bound}") from error
    return value


def _directory(name, default):
    value = os.environ.get(name, default)
    if not value.strip():
        raise ConfigurationError(f"{name} must name a directory")
    return Path(value).resolve()


def _check_directory(name, path):
    try:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        # A real create/write check works for non-root containers and mounted
        # volumes. It leaves no published result and never runs result cleanup.
        with tempfile.TemporaryFile(dir=path) as probe:
            probe.write(b"geo-processes startup check")
            probe.flush()
    except OSError as error:
        raise ConfigurationError(f"{name} must be a writable directory: {path}") from error


@dataclass(frozen=True)
class RuntimeSettings:
    url: str
    processes: tuple[str, ...]
    input_dir: Path
    allowed_hosts: tuple[str, ...]
    store: ResultStore
    port: int
    workers: int
    timeout: int

    def summary(self):
        return "\n".join(
            [
                "geo-processes startup configuration:",
                f"  Public URL: {self.url}",
                f"  Processes: {', '.join(self.processes) or '(none)'}",
                f"  Gunicorn: port {self.port}, {self.workers} sync workers, timeout {self.timeout}s",
                f"  Inputs: {engine.MAX_INPUT_BYTES} bytes, {engine.MAX_SAMPLES} samples, "
                f"{MAX_EXECUTION_BYTES} request bytes, {INPUT_SLOTS} slots at {self.input_dir}",
                f"  HTTPS hosts: {', '.join(self.allowed_hosts) or 'any public destination'} (port 443; TLS verified)",
                f"  Results: {self.store.root}; retention {self.store.retention_seconds}s, "
                f"{self.store.max_bytes} bytes, {self.store.max_results} files",
            ]
        )


def validate_runtime(config):
    """Resolve and check settings, without executing processes or purging data."""
    url = public_url(config["server"]["url"])
    input_dir = _directory("GEO_INPUT_TMPDIR", "runtime-data/inputs")
    output_dir = _directory("GEO_OUTPUT_DIR", "runtime-data/results")
    allowed_hosts = _allowed_hosts()
    # Name the exact variable for integer syntax errors; ResultStore retains
    # ownership of the existing retention and capacity bounds.
    for name, default in (
        ("GEO_RESULT_RETENTION_SECONDS", 86400),
        ("GEO_RESULT_MAX_BYTES", 64 * 1024 * 1024),
        ("GEO_RESULT_MAX_COUNT", 256),
    ):
        _positive_integer(name, default)
    try:
        store = ResultStore.from_environment()
    except ValueError as error:
        raise ConfigurationError(f"GEO_RESULT_* settings: {error}") from error
    if input_dir == output_dir or input_dir in output_dir.parents or output_dir in input_dir.parents:
        raise ConfigurationError("GEO_INPUT_TMPDIR and GEO_OUTPUT_DIR must be separate, non-nested directories")
    settings = RuntimeSettings(
        url,
        tuple(sorted(key for key, resource in config["resources"].items() if resource["type"] == "process")),
        input_dir,
        allowed_hosts,
        store,
        _positive_integer("CONTAINER_PORT", 8080, 65535),
        _positive_integer("WSGI_WORKERS", 2),
        _positive_integer("WSGI_WORKER_TIMEOUT", 30),
    )
    _check_directory("GEO_INPUT_TMPDIR", input_dir)
    _check_directory("GEO_OUTPUT_DIR", output_dir)
    return settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/pygeoapi.yml"))
    args = parser.parse_args()
    try:
        with args.config.open(encoding="utf-8") as stream:
            settings = validate_runtime(yaml_load(stream))
    except (ConfigurationError, OSError) as error:
        print(f"Startup configuration error: {error}", file=sys.stderr)
        return 1
    print(settings.summary(), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
