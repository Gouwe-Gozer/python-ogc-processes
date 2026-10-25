"""Run the pinned Geonovum checker and compare exact diagnostics."""

from __future__ import annotations

import argparse
import json
import os
import shutil

# The checker runs without a shell and with a fixed argument vector.
import subprocess  # nosec B404
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

CHECKER_PACKAGE = "@geonovum/ogc-checker"
CHECKER_VERSION = "1.3.2"
NODE_IMAGE = "node:24.22.1-alpine@sha256:06d7adf3e0ef61a13f1d28682726366f97a15aa1888c934d3ecec86c33918b53"
STANDARD = "ogc-api-processes"
STANDARD_VERSION = "1.0.0"
CHECKER_TIMEOUT_SECONDS = 120
DEFAULT_ATTEMPTS = 5

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = PROJECT_ROOT / "validation" / "geonovum" / "baseline.json"

EXIT_BASELINE_MISMATCH = 1
EXIT_OPERATIONAL_ERROR = 2

NETWORK_FAILURE_MARKERS = (
    "socket hang up",
    "econnreset",
    "econnrefused",
    "enotfound",
    "etimedout",
    "fetch failed",
    "network error",
)
SCHEMA_TIMEOUT_MARKERS = (
    "timed out resolving $refs",
    "timeout resolving $refs",
)


class CheckerOperationalError(RuntimeError):
    """Raised when the checker cannot produce a complete diagnostic report."""


def diagnostic_identity(diagnostic: dict[str, Any]) -> tuple[str, tuple[str | int, ...], str]:
    """Identify one rule finding independently of mutable explanatory fields."""
    return (
        diagnostic["code"],
        tuple(diagnostic["path"]),
        diagnostic["source"],
    )


def normalize_diagnostic(diagnostic: Any) -> dict[str, Any]:
    """Validate and retain stable fields, including the 1.3 conformance-class URI."""
    if not isinstance(diagnostic, dict):
        raise CheckerOperationalError("Checker returned a non-object diagnostic")

    required_types = {
        "severity": str,
        "message": str,
        "code": str,
        "path": list,
        "source": str,
    }
    for field, expected_type in required_types.items():
        if not isinstance(diagnostic.get(field), expected_type):
            raise CheckerOperationalError(f"Checker diagnostic has invalid or missing {field!r}")

    path = diagnostic["path"]
    if not all(isinstance(component, str | int) for component in path):
        raise CheckerOperationalError("Checker diagnostic path contains an unsupported value")

    normalized = {
        "severity": diagnostic["severity"],
        "code": diagnostic["code"],
        "message": diagnostic["message"],
        "path": path,
        "source": diagnostic["source"],
    }
    documentation_url = diagnostic.get("documentationUrl")
    if documentation_url is not None:
        if not isinstance(documentation_url, str):
            raise CheckerOperationalError("Checker diagnostic has an invalid documentationUrl")
        normalized["documentationUrl"] = documentation_url
    if "ruleset" in diagnostic:
        if not isinstance(diagnostic["ruleset"], str):
            raise CheckerOperationalError("Checker diagnostic has an invalid ruleset")
        normalized["ruleset"] = diagnostic["ruleset"]
    return normalized


def normalize_report(report: Any, input_url: str | None = None) -> dict[str, Any]:
    """Convert checker output into the stable repository baseline format."""
    if not isinstance(report, dict):
        raise CheckerOperationalError("Checker output is not a JSON object")
    if not isinstance(report.get("diagnostics"), list):
        raise CheckerOperationalError("Checker output has no diagnostics array")
    if not isinstance(report.get("rulesets"), list) or not all(
        isinstance(ruleset, str) for ruleset in report["rulesets"]
    ):
        raise CheckerOperationalError("Checker output has no valid rulesets array")

    diagnostics = [normalize_diagnostic(item) for item in report["diagnostics"]]
    for diagnostic in diagnostics:
        # The checker reports the tested URL as source. Keep comparisons
        # independent of the local port without masking other source changes.
        if input_url is not None and diagnostic["source"] == input_url:
            diagnostic["source"] = "<input>"
    diagnostics.sort(key=lambda item: json.dumps(diagnostic_identity(item), separators=(",", ":")))

    identities = [diagnostic_identity(item) for item in diagnostics]
    if len(identities) != len(set(identities)):
        raise CheckerOperationalError("Checker returned duplicate diagnostic identities")

    return {
        "schemaVersion": 1,
        "checker": {
            "package": CHECKER_PACKAGE,
            "version": CHECKER_VERSION,
        },
        "standard": {
            "id": STANDARD,
            "version": STANDARD_VERSION,
        },
        "rulesets": report["rulesets"],
        "diagnostics": diagnostics,
    }


def transient_diagnostics(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Return network-dependent diagnostics that make a run incomplete."""
    transient = []
    for raw_diagnostic in report.get("diagnostics", []):
        if not isinstance(raw_diagnostic, dict):
            continue
        message = str(raw_diagnostic.get("message", ""))
        lowered = message.lower()
        is_network_ref_failure = raw_diagnostic.get("code") == "invalid-ref" and any(
            marker in lowered for marker in NETWORK_FAILURE_MARKERS
        )
        is_schema_timeout = any(marker in lowered for marker in SCHEMA_TIMEOUT_MARKERS)
        if is_network_ref_failure or is_schema_timeout:
            transient.append(raw_diagnostic)
    return transient


def checker_command(npx: str, input_url: str) -> list[str]:
    return [
        npx,
        "--yes",
        f"{CHECKER_PACKAGE}@{CHECKER_VERSION}",
        "validate",
        "--standard",
        STANDARD,
        "--version",
        STANDARD_VERSION,
        "--input",
        input_url,
        "--format",
        "json",
        "--fail-on",
        "none",
    ]


def container_command(input_url: str) -> list[str]:
    """Use a pinned runtime and npm lockfile without installing host Node tools."""
    checker = PROJECT_ROOT / "validation/geonovum"
    cache = PROJECT_ROOT / "runtime-data/validation/npm-cache"
    cache.mkdir(parents=True, exist_ok=True)
    package = json.loads((checker / "package.json").read_text())
    if package["dependencies"][CHECKER_PACKAGE] != CHECKER_VERSION:
        raise CheckerOperationalError("Checker version and npm manifest disagree")
    return [
        "docker",
        "run",
        "--rm",
        "--name",
        "raster-geonovum-" + uuid4().hex[:12],
        "--network",
        "host",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--mount",
        f"type=bind,src={checker},dst=/checker",
        "--mount",
        f"type=bind,src={cache},dst=/npm-cache",
        "--env",
        "npm_config_cache=/npm-cache",
        "--entrypoint",
        "/bin/sh",
        NODE_IMAGE,
        "-c",
        "npm ci --prefix /checker --ignore-scripts --no-audit --no-fund >&2 && "
        'exec node /checker/node_modules/@geonovum/ogc-checker/dist/cli.mjs "$@"',
        "checker",
        *checker_command("npx", input_url)[3:],
    ]


def run_checker(
    input_url: str,
    attempts: int,
    raw_output: Path | None = None,
    *,
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    wait: Callable[[float], None] = time.sleep,
    use_docker: bool = False,
) -> dict[str, Any]:
    """Run the checker, retrying only incomplete operational attempts."""
    npx = shutil.which("npx")
    if npx is None and not use_docker:
        raise CheckerOperationalError("npx was not found; install Node.js 24 LTS (the CI runtime)")

    last_problem = "checker did not run"
    last_output = ""
    for attempt in range(1, attempts + 1):
        arguments = container_command(input_url) if use_docker else checker_command(npx, input_url)
        try:
            result = command_runner(
                arguments,
                capture_output=True,
                text=True,
                timeout=CHECKER_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            last_problem = f"checker command failed: {error}"
        else:
            last_output = result.stdout
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip() or "no output"
                last_problem = f"checker exited with status {result.returncode}: {detail}"
            else:
                try:
                    report = json.loads(result.stdout)
                except json.JSONDecodeError as error:
                    last_problem = f"checker returned invalid JSON: {error}"
                else:
                    if raw_output is not None:
                        write_json(raw_output, report)
                    transient = transient_diagnostics(report)
                    if not transient:
                        return normalize_report(report, input_url)
                    codes = ", ".join(str(item.get("code", "unknown")) for item in transient)
                    last_problem = f"incomplete schema resolution ({codes})"
        finally:
            # Killing the Docker CLI on timeout does not guarantee that its
            # container stopped. Scope cleanup to the unique name we created.
            if use_docker:
                name = arguments[arguments.index("--name") + 1]
                try:
                    command_runner(
                        ["docker", "rm", "--force", name],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        check=False,
                    )
                except (OSError, subprocess.TimeoutExpired) as error:
                    raise CheckerOperationalError(f"Could not clean up checker container {name}: {error}") from error

        if attempt < attempts:
            print(f"Checker attempt {attempt}/{attempts} incomplete: {last_problem}; retrying", file=sys.stderr)
            wait(2)

    if raw_output is not None and last_output:
        try:
            write_json(raw_output, json.loads(last_output))
        except json.JSONDecodeError:
            raw_output.parent.mkdir(parents=True, exist_ok=True)
            raw_output.write_text(last_output, encoding="utf-8")
    raise CheckerOperationalError(f"Checker produced no complete report after {attempts} attempts: {last_problem}")


def write_json(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_baseline(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as source:
            baseline = json.load(source)
    except FileNotFoundError as error:
        raise CheckerOperationalError(f"Baseline does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise CheckerOperationalError(f"Baseline is not valid JSON: {error}") from error

    if not isinstance(baseline, dict) or not isinstance(baseline.get("diagnostics"), list):
        raise CheckerOperationalError("Baseline has an invalid structure")
    return baseline


def compare_reports(
    baseline: dict[str, Any], current: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[dict[str, Any], dict[str, Any]]], list[str]]:
    """Return added, removed and changed diagnostics plus metadata changes."""
    baseline_index = {diagnostic_identity(item): item for item in baseline["diagnostics"]}
    current_index = {diagnostic_identity(item): item for item in current["diagnostics"]}

    added = [current_index[key] for key in sorted(current_index.keys() - baseline_index.keys())]
    removed = [baseline_index[key] for key in sorted(baseline_index.keys() - current_index.keys())]
    changed = [
        (baseline_index[key], current_index[key])
        for key in sorted(baseline_index.keys() & current_index.keys())
        if baseline_index[key] != current_index[key]
    ]

    metadata_changes = []
    for field in ("schemaVersion", "checker", "standard", "rulesets"):
        if baseline.get(field) != current.get(field):
            metadata_changes.append(field)
    return added, removed, changed, metadata_changes


def describe_diagnostic(diagnostic: dict[str, Any]) -> str:
    path = "/".join(str(component) for component in diagnostic["path"]) or "<document>"
    return f"{diagnostic['code']} at {path} (source: {diagnostic['source']}): {diagnostic['message']}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="http://127.0.0.1:5001/openapi?f=json", help="OpenAPI document URL")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE, help="Diagnostic baseline JSON")
    parser.add_argument("--raw-output", type=Path, help="Write the latest unnormalised checker report here")
    parser.add_argument(
        "--docker", action="store_true", help="Use the pinned Node image and npm lockfile (Linux host networking)"
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=DEFAULT_ATTEMPTS,
        help=f"Maximum checker attempts after operational failures (default: {DEFAULT_ATTEMPTS})",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Replace the baseline after a complete run; never use this option in CI",
    )
    args = parser.parse_args()

    if args.attempts < 1:
        parser.error("--attempts must be at least 1")

    try:
        current = run_checker(args.input, args.attempts, args.raw_output, use_docker=args.docker)
        if args.update_baseline:
            write_json(args.baseline, current)
            print(f"UPDATED Geonovum baseline with {len(current['diagnostics'])} diagnostics: {args.baseline}")
            return 0

        baseline = load_baseline(args.baseline)
        added, removed, changed, metadata_changes = compare_reports(baseline, current)
    except CheckerOperationalError as error:
        print(f"OPERATIONAL ERROR: {error}", file=sys.stderr)
        return EXIT_OPERATIONAL_ERROR

    if not (added or removed or changed or metadata_changes):
        print(f"PASS Geonovum diagnostics match the {len(current['diagnostics'])}-diagnostic baseline")
        return 0

    print("FAIL Geonovum diagnostics differ from the reviewed baseline")
    for field in metadata_changes:
        print(f"  METADATA CHANGED: {field}")
    for diagnostic in added:
        print(f"  ADDED: {describe_diagnostic(diagnostic)}")
    for diagnostic in removed:
        print(f"  REMOVED: {describe_diagnostic(diagnostic)}")
    for previous, diagnostic in changed:
        print(f"  CHANGED: {describe_diagnostic(diagnostic)}")
        print(f"    previous: {previous}")
        print(f"    current:  {diagnostic}")
    if removed and not (added or changed or metadata_changes):
        print("A known diagnostic was resolved. Review the result and update the baseline in this pull request.")
    return EXIT_BASELINE_MISMATCH


if __name__ == "__main__":
    raise SystemExit(main())
