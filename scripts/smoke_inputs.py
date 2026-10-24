"""Submit an independent GeoTIFF, inspect it, reproject it and download results."""

import argparse
import base64
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.io import MemoryFile

from scripts.smoke_warp import _read, run


def synthetic_raster():
    """Create test data independently of the service's bundled demo."""
    pixels = np.arange(2 * 64 * 48, dtype="uint16").reshape(2, 48, 64)
    pixels[0, 0, 0] = 65535
    with MemoryFile() as memory:
        with memory.open(
            driver="GTiff",
            width=64,
            height=48,
            count=2,
            dtype="uint16",
            crs="EPSG:28992",
            transform=rasterio.Affine(10, 0, 155000, 0, -10, 463000),
            nodata=65535,
        ) as dataset:
            dataset.write(pixels)
        return memory.read()


def check(base_url, data, *, href=None):
    with MemoryFile(data) as memory, memory.open() as original:
        shape, bands = original.shape, original.count
        expected_crs = original.crs.to_epsg() if original.crs else None
    source = (
        {"href": href, "type": "image/tiff"}
        if href
        else {
            "value": base64.b64encode(data).decode("ascii"),
            "mediaType": "image/tiff",
            "encoding": "base64",
        }
    )
    for mode in ("raw", "document"):
        payload = {"inputs": {"source": source}, "response": mode}
        status, headers, result = _read(f"{base_url.rstrip('/')}/processes/raster-info/execution", payload)
        if status != 200 or headers.get_content_type() != "application/json":
            raise RuntimeError("user-raster information did not return HTTP 200 JSON")
        info = json.loads(result)
        if mode == "document":
            info = info["info"]["value"]
        if info["size"] != [shape[1], shape[0]] or info["band_count"] != bands:
            raise RuntimeError("service did not inspect the supplied raster dimensions/bands")
        if info["crs"] is None or info["crs"]["epsg"] != expected_crs:
            raise RuntimeError("service did not inspect the supplied raster CRS")
        print(f"PASS {mode} info describes the independently supplied raster")
    run(base_url, source=source, shape=shape, bands=bands)
    print("PASS user-supplied raster inspection, all warp modes and independent result downloads")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:5001")
    parser.add_argument("--input-raster", type=Path, help="Use your own GeoTIFF instead of generated test data")
    parser.add_argument("--source-href", help="Fetch this HTTPS copy of --input-raster instead of submitting inline")
    args = parser.parse_args()
    if args.source_href and args.input_raster is None:
        parser.error("--source-href needs --input-raster for independent comparison")
    data = args.input_raster.read_bytes() if args.input_raster else synthetic_raster()
    check(args.base_url, data, href=args.source_href)


if __name__ == "__main__":
    main()
