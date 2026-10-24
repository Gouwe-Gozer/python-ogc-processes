"""Check container discovery and execute the bounded Rasterio process."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from typing import Any

from geo_processes.datasets import demo_source

PROCESS_ID = "raster-info"


class SmokeTestError(RuntimeError):
    """Raised when the running API does not meet a smoke-test expectation."""


def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _validate_base_url(base_url: str) -> None:
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SmokeTestError("base URL must be an absolute HTTP or HTTPS URL")


def _get_json(base_url: str, path: str) -> dict[str, Any]:
    url = _url(base_url, path)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})  # noqa: S310

    try:
        # The caller validates that base_url uses only HTTP or HTTPS.
        with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310
            content_type = response.headers.get("Content-Type", "").lower()
            if response.status != 200:
                raise SmokeTestError(f"GET {path} returned HTTP {response.status}")
            if "json" not in content_type:
                raise SmokeTestError(f"GET {path} returned unexpected Content-Type {content_type!r}")
            document = json.load(response)
    except (OSError, json.JSONDecodeError) as error:
        raise SmokeTestError(f"GET {path} failed: {error}") from error

    if not isinstance(document, dict):
        raise SmokeTestError(f"GET {path} did not return a JSON object")

    print(f"PASS GET {path} returned JSON")
    return document


def _wait_until_ready(base_url: str, wait_seconds: int) -> None:
    deadline = time.monotonic() + wait_seconds
    last_error: SmokeTestError | None = None

    while time.monotonic() < deadline:
        try:
            _get_json(base_url, "/conformance")
            print("PASS API became ready")
            return
        except SmokeTestError as error:
            last_error = error
            time.sleep(2)

    raise SmokeTestError(f"API did not become ready within {wait_seconds} seconds: {last_error}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeTestError(message)
    print(f"PASS {message}")


def run(base_url: str, wait_seconds: int) -> None:
    """Run discovery checks against a running service."""
    _validate_base_url(base_url)
    _wait_until_ready(base_url, wait_seconds)

    landing_page = _get_json(base_url, "/")
    conformance = _get_json(base_url, "/conformance")
    openapi = _get_json(base_url, "/openapi?f=json")
    process_list = _get_json(base_url, "/processes")
    process = _get_json(base_url, f"/processes/{PROCESS_ID}")

    links = landing_page.get("links")
    _require(isinstance(links, list) and len(links) > 0, "landing page advertises links")

    conforms_to = conformance.get("conformsTo")
    _require(isinstance(conforms_to, list) and len(conforms_to) > 0, "conformance declaration is not empty")

    paths = openapi.get("paths")
    expected_paths = {
        "/",
        "/conformance",
        "/openapi",
        "/processes",
        f"/processes/{PROCESS_ID}",
        f"/processes/{PROCESS_ID}/execution",
    }
    _require(str(openapi.get("openapi", "")).startswith("3."), "runtime document uses OpenAPI 3")
    _require(isinstance(paths, dict), "runtime OpenAPI document contains paths")
    missing_paths = expected_paths - set(paths)
    _require(not missing_paths, f"runtime OpenAPI advertises required paths (missing: {sorted(missing_paths)})")

    processes = process_list.get("processes")
    process_ids = (
        {item.get("id") for item in processes if isinstance(item, dict)} if isinstance(processes, list) else set()
    )
    _require(PROCESS_ID in process_ids, f"process list contains {PROCESS_ID}")
    _require(process.get("id") == PROCESS_ID, f"process description identifies {PROCESS_ID}")

    results = {}
    for mode in ("raw", "document"):
        payload = json.dumps({"inputs": {"source": demo_source()}, "response": mode}).encode()
        request = urllib.request.Request(
            _url(base_url, f"/processes/{PROCESS_ID}/execution"),
            data=payload,
            headers={"Content-Type": "application/json", "Prefer": "respond-async"},
        )
        # base_url was validated above; the client intentionally reaches this service.
        with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310
            _require(response.status == 200, f"{mode} execution returns HTTP 200")
            _require(response.headers.get_content_type() == "application/json", "execution returns application/json")
            _require("Location" not in response.headers, "execution does not promise an async job")
            results[mode] = json.load(response)
    _require(results["document"] == {"info": {"value": results["raw"]}}, "document result matches raw output")
    _require(results["raw"]["size"] == [4, 3], "Rasterio inspected the bundled 4 by 3 raster")
    _require(results["raw"]["bands"][0]["statistics"]["mean"] == 6.5, "Rasterio computed exact band statistics")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:5001")
    parser.add_argument("--wait-seconds", type=int, default=60)
    args = parser.parse_args()

    try:
        run(args.base_url, args.wait_seconds)
    except SmokeTestError as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1

    print("PASS container discovery smoke test completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
