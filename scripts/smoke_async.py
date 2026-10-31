"""Exercise sync and durable async raster execution through an HTTP client."""

import argparse
import base64
import time
from urllib.parse import urlsplit

import requests
from rasterio.io import MemoryFile

from scripts.smoke_inputs import synthetic_raster


def successful(response, expected=200):
    if response.status_code != expected:
        raise RuntimeError(f"Expected HTTP {expected}, received {response.status_code}: {response.text[:1000]}")
    return response


def execute(base_url, process, document):
    response = successful(
        requests.post(
            f"{base_url}/processes/{process}/execution",
            json=document,
            headers={"Prefer": "respond-async"},
            timeout=10,
        ),
        201,
    )
    job = response.json()
    location = response.headers.get("Location", "")
    if response.headers.get("Preference-Applied") != "respond-async" or location != f"{base_url}/jobs/{job['jobID']}":
        raise RuntimeError("Async acceptance did not provide its canonical job URL and applied preference")
    if job.get("type") != "process" or job.get("status") != "accepted":
        raise RuntimeError("Async acceptance did not contain the required status information")
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        status = successful(requests.get(location, timeout=5)).json()
        if status["status"] == "successful":
            return successful(requests.get(location + "/results", timeout=10))
        if status["status"] == "failed":
            failure = requests.get(location + "/results", timeout=5)
            raise RuntimeError(f"Async execution failed: {failure.status_code} {failure.text[:1000]}")
        pending = requests.get(location + "/results", timeout=5)
        if pending.status_code not in {200, 204, 404}:
            raise RuntimeError(f"Unexpected pending result response: {pending.status_code}")
        if pending.status_code == 404 and pending.json().get("code") != "ResultNotReady":
            raise RuntimeError("Pending job did not return ResultNotReady")
        time.sleep(0.2)
    raise RuntimeError("Async job did not complete within 60 seconds")


def check(base_url):
    source = {"value": base64.b64encode(synthetic_raster()).decode(), "mediaType": "image/tiff", "encoding": "base64"}
    info = {"inputs": {"source": source}, "response": "document"}
    sync = successful(requests.post(f"{base_url}/processes/raster-info/execution", json=info, timeout=30))
    if "Location" in sync.headers:
        raise RuntimeError("Unretained synchronous execution advertised a job Location")
    asynchronous = execute(base_url, "raster-info", info)
    if asynchronous.json() != sync.json():
        raise RuntimeError("Sync and async information outputs differ")
    print("PASS synchronous execution and durable async information results agree", flush=True)
    warped = execute(
        base_url,
        "raster-warp",
        {
            "inputs": {"source": source, "target_crs": "EPSG:4326"},
            "response": "document",
            "outputs": {"result": {"transmissionMode": "reference"}},
        },
    ).json()["result"]
    if urlsplit(warped["href"]).netloc != urlsplit(base_url).netloc:
        raise RuntimeError("Async result reference does not use the configured public URL")
    downloaded = successful(requests.get(warped["href"], timeout=10))
    with MemoryFile(downloaded.content) as memory, memory.open() as raster:
        if raster.crs.to_epsg() != 4326 or raster.shape != (48, 64):
            raise RuntimeError("Async warp output has unexpected CRS or dimensions")
    print("PASS durable async warp, job status/results and independent GeoTIFF download", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5001")
    check(parser.parse_args().base_url.rstrip("/"))


if __name__ == "__main__":
    main()
