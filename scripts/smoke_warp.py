"""Execute all warp response modes and open downloads from an independent client."""

import argparse
import base64
import json
import urllib.parse
import urllib.request
from pathlib import Path

from rasterio.io import MemoryFile


def _read(url, payload=None):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("expected an absolute HTTP or HTTPS URL")
    request = urllib.request.Request(
        url,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    # The operator selects this URL, and the server supplies the result URL.
    with urllib.request.urlopen(request, timeout=15) as response:  # nosec B310
        return response.status, response.headers, response.read()


def _inspect(data, shape=(3, 4), bands=1):
    with MemoryFile(data) as memory, memory.open() as raster:
        if raster.crs.to_epsg() != 4326 or raster.shape != shape or raster.count != bands:
            raise RuntimeError("downloaded GeoTIFF has unexpected CRS or dimensions")
        if raster.read(1, masked=True).count() == 0:
            raise RuntimeError("downloaded GeoTIFF has no valid samples")


def check_reference(url, shape=(3, 4), bands=1):
    status, headers, data = _read(url)
    if status != 200 or headers.get_content_type() != "image/tiff":
        raise RuntimeError("result reference did not return a GeoTIFF")
    if not headers.get("Expires") or headers.get("Cache-Control") != "no-store":
        raise RuntimeError("result download does not describe its lifetime")
    _inspect(data, shape, bands)
    print("PASS independent HTTP client downloaded and opened the referenced GeoTIFF")


def run(base_url, save_reference=None, *, source=None, shape=(3, 4), bands=1):
    if source is None:
        from geo_processes.datasets import demo_source

        source = demo_source()
    reference = None
    for mode in ("raw", "document"):
        for transmission in ("value", "reference"):
            payload = {
                "inputs": {"source": source, "target_crs": "EPSG:4326"},
                "response": mode,
                "outputs": {"result": {"transmissionMode": transmission}},
            }
            status, headers, data = _read(f"{base_url.rstrip('/')}/processes/raster-warp/execution", payload)
            if headers.get("Location") or headers.get("Preference-Applied") or headers.get("X-Geo-Internal-Status"):
                raise RuntimeError("synchronous execution leaked a job or private transport header")
            if mode == "raw" and transmission == "reference":
                if status != 204 or data:
                    raise RuntimeError("raw/reference must return 204 with an empty body")
                reference = headers["Link"].split("<", 1)[1].split(">", 1)[0]
                check_reference(reference, shape, bands)
            else:
                if status != 200:
                    raise RuntimeError("execution did not return 200")
                if mode == "document":
                    if headers.get_content_type() != "application/json":
                        raise RuntimeError("document result must be application/json")
                    result = json.loads(data)["result"]
                    if transmission == "reference":
                        reference = result["href"]
                        if result["type"] != "image/tiff":
                            raise RuntimeError("reference does not declare image/tiff")
                        check_reference(reference, shape, bands)
                    else:
                        if result["encoding"] != "base64" or result["mediaType"] != "image/tiff":
                            raise RuntimeError("inline output must describe its binary encoding")
                        _inspect(base64.b64decode(result["value"], validate=True), shape, bands)
                else:
                    if headers.get_content_type() != "image/tiff":
                        raise RuntimeError("raw/value must be image/tiff")
                    _inspect(data, shape, bands)
            print(f"PASS {mode}/{transmission} has the expected HTTP representation")
    if save_reference is not None:
        save_reference.write_text(reference + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:5001")
    parser.add_argument("--save-reference", type=Path)
    parser.add_argument("--check-saved-reference", type=Path)
    args = parser.parse_args()
    if args.check_saved_reference is not None:
        check_reference(args.check_saved_reference.read_text().strip())
    else:
        run(args.base_url, args.save_reference)


if __name__ == "__main__":
    main()
