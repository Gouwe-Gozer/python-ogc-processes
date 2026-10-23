#!/usr/bin/env python3
"""Verify the isolation properties of the running release container."""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404
from pathlib import Path, PurePosixPath


def _run(command: list[str]) -> str:
    """Run one fixed Docker CLI command and return standard output."""

    # The executable and arguments are fixed and passed without a shell.
    result = subprocess.run(  # nosec B603
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def inspect_service(compose_file: Path, service: str, project_name: str | None) -> dict:
    """Return Docker's inspection document for one Compose service."""

    compose_command = ["docker", "compose"]
    if project_name is not None:
        compose_command.extend(["--project-name", project_name])
    compose_command.extend(["--file", str(compose_file), "ps", "--quiet", service])

    container_id = _run(compose_command)
    if not container_id:
        raise RuntimeError(f"Compose service is not running: {service}")

    inspection = json.loads(_run(["docker", "inspect", container_id]))
    if not isinstance(inspection, list) or len(inspection) != 1:
        raise RuntimeError("Docker inspect did not return exactly one container")
    return inspection[0]


def validate_release_container(inspection: dict) -> None:
    """Raise an error if the container is not isolated as documented."""

    user = inspection["Config"].get("User", "")
    user_id = user.split(":", 1)[0]
    if not user_id or user_id in {"0", "root"}:
        raise RuntimeError("Release container must run as a non-root user")
    print(f"PASS release container runs as non-root user {user}")

    host_config = inspection["HostConfig"]
    if host_config.get("ReadonlyRootfs") is not True:
        raise RuntimeError("Release container root filesystem must be read-only")
    print("PASS release container root filesystem is read-only")

    mounts = inspection.get("Mounts", [])
    if (
        len(mounts) != 1
        or mounts[0].get("Type") != "volume"
        or mounts[0].get("Destination") != "/var/lib/geo/results"
        or mounts[0].get("RW") is not True
    ):
        raise RuntimeError("Release container must have only its writable named result volume")
    print("PASS release container has only its dedicated named result volume, without host bind mounts")

    dropped_capabilities = set(host_config.get("CapDrop") or [])
    if "ALL" not in dropped_capabilities:
        raise RuntimeError("Release container must drop all Linux capabilities")
    print("PASS release container drops all Linux capabilities")

    security_options = set(host_config.get("SecurityOpt") or [])
    if "no-new-privileges:true" not in security_options:
        raise RuntimeError("Release container must prevent privilege escalation")
    print("PASS release container prevents privilege escalation")

    # This verifies the intentional container mount; it does not create a file.
    runtime_directory = PurePosixPath("/", "tmp").as_posix()
    if runtime_directory not in (host_config.get("Tmpfs") or {}):
        raise RuntimeError("Release container must provide ephemeral runtime storage at /tmp")
    print("PASS release container uses ephemeral runtime storage")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compose-file", type=Path, default=Path("compose.release.yml"))
    parser.add_argument("--service", default="api")
    parser.add_argument("--project-name")
    args = parser.parse_args()

    validate_release_container(inspect_service(args.compose_file, args.service, args.project_name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
