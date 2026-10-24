"""Inspect and reproject a local GeoTIFF through the API, then save its result."""

import argparse
import base64
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from geo_processes.contracts.warp import RESAMPLING_METHODS, TARGET_CRSS
from geo_processes.engine import MAX_INPUT_BYTES
from geo_processes.startup import public_url
from geo_processes.storage import MAX_RESULT_BYTES

MAX_JSON_BYTES = 4 * 1024 * 1024


class ClientError(RuntimeError):
    """A local-file or API failure that can be shown without a traceback."""


def _open(url, payload=None):
    public_url(url)  # Only absolute HTTP(S); never file:// or embedded credentials.
    headers = {"Accept": "application/json" if payload is not None else "image/tiff"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        # public_url() restricts the operator-selected URL to HTTP(S).
        return urllib.request.urlopen(request, timeout=60)  # nosec B310
    except urllib.error.HTTPError as error:
        with error:
            body = error.read(4096)
        try:
            document = json.loads(body)
            detail = document.get("detail") or document.get("description") or error.reason
        except (ValueError, AttributeError):
            detail = error.reason
        raise ClientError(f"API returned HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise ClientError(f"Could not reach the API: {error.reason}") from error


def _execute(base_url, process, payload):
    with _open(f"{base_url}/processes/{process}/execution", payload) as response:
        if response.status != 200 or response.headers.get_content_type() != "application/json":
            raise ClientError(f"{process} did not return HTTP 200 JSON")
        body = response.read(MAX_JSON_BYTES + 1)
    if len(body) > MAX_JSON_BYTES:
        raise ClientError("API JSON response exceeds this client's 4 MiB limit")
    try:
        return json.loads(body)
    except ValueError as error:
        raise ClientError("API returned invalid JSON") from error


def process_raster(base_url, source_path, output_path, *, target_crs="EPSG:4326", resampling="bilinear"):
    """Use ordinary OGC inline input and document/reference output requests."""
    base_url = public_url(base_url)
    if output_path.exists():
        raise ClientError(f"Output already exists: {output_path}; choose another path")
    with source_path.open("rb") as source:
        data = source.read(MAX_INPUT_BYTES + 1)
    if not data or len(data) > MAX_INPUT_BYTES:
        raise ClientError("Input must be a non-empty GeoTIFF of at most 16 MiB")
    source = {"value": base64.b64encode(data).decode("ascii"), "mediaType": "image/tiff", "encoding": "base64"}
    info = _execute(base_url, "raster-info", {"inputs": {"source": source}})
    try:
        width, height = info["size"]
        print(f"Source: {width} x {height}, {info['band_count']} band(s)")
        document = _execute(
            base_url,
            "raster-warp",
            {
                "inputs": {"source": source, "target_crs": target_crs, "resampling": resampling},
                "response": "document",
                "outputs": {"result": {"transmissionMode": "reference"}},
            },
        )
        result = document["result"]
        if result["type"] != "image/tiff" or not isinstance(result["href"], str):
            raise ClientError("API did not return a GeoTIFF download reference")
    except (KeyError, TypeError, ValueError) as error:
        raise ClientError("API returned an unexpected information or result document") from error
    with tempfile.TemporaryDirectory(prefix=".geo-processes-", dir=output_path.parent) as workspace:
        staged = Path(workspace) / "output.tif"
        with _open(result["href"]) as response:
            if response.status != 200 or response.headers.get_content_type() != "image/tiff":
                raise ClientError("Result download did not return HTTP 200 image/tiff")
            length = response.headers.get("Content-Length")
            expected = int(length) if length is not None else None
            count = 0
            with staged.open("wb") as output:
                while chunk := response.read(64 * 1024):
                    count += len(chunk)
                    if count > MAX_RESULT_BYTES:
                        raise ClientError("Result exceeds the 16 MiB output limit")
                    output.write(chunk)
        if not count or (expected is not None and count != expected):
            raise ClientError("Result download was empty or incomplete")
        # Publish only the complete download. link() also refuses a file created
        # at the destination during the request; no existing file is overwritten.
        os.link(staged, output_path)
    print(f"Saved {target_crs} GeoTIFF to {output_path} ({count} bytes)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Your local GeoTIFF (maximum 16 MiB)")
    parser.add_argument("--output", type=Path, required=True, help="New local filename; existing files are preserved")
    parser.add_argument("--base-url", default="http://localhost:5001", help="Canonical API URL, including any prefix")
    parser.add_argument("--target-crs", choices=TARGET_CRSS, default="EPSG:4326")
    parser.add_argument("--resampling", choices=RESAMPLING_METHODS, default="bilinear")
    args = parser.parse_args()
    try:
        process_raster(args.base_url, args.input, args.output, target_crs=args.target_crs, resampling=args.resampling)
    except (ClientError, OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
