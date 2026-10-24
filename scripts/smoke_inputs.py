"""Submit an independent GeoTIFF, inspect it, reproject it and download results."""

import argparse
import base64
import json
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.warp import transform

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
    check_operations(base_url, source, data)
    print("PASS user-supplied raster inspection, all warp modes and independent result downloads")


def check_operations(base_url, source, data):
    """Check native GeoJSON, reclassification and vector download delivery."""
    with MemoryFile(data) as memory, memory.open() as raster:
        x, y = raster.xy(0, min(1, raster.width - 1))
        longitude, latitude = transform(raster.crs, "EPSG:4326", [x], [y])
        expected_sample = raster.read(1, masked=True)[0, min(1, raster.width - 1)]
        values = np.ma.masked_invalid(raster.read(1, masked=True).astype("float64"))
        if not values.count():
            raise RuntimeError("operation smoke checks need at least one finite, valid pixel")
        lower, upper = float(values.min()), float(np.nextafter(float(values.max()), np.inf))
        polygon_supported = raster.width * raster.height <= 65536
    expected = None if np.ma.is_masked(expected_sample) or not np.isfinite(expected_sample) else expected_sample.item()
    point = {"type": "Point", "coordinates": [longitude[0], latitude[0]]}
    point_collection = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {}, "geometry": point}],
    }
    multipoint = {"type": "MultiPoint", "coordinates": [point["coordinates"], point["coordinates"]]}
    for locations, count in ((point, 1), (multipoint, 2), (point_collection, 1)):
        sample_payload = {"inputs": {"source": source, "points": {"value": locations}}}
        status, headers, result = _read(
            f"{base_url.rstrip('/')}/processes/raster-sample-points/execution", sample_payload
        )
        if status != 200 or headers.get_content_type() != "application/geo+json":
            raise RuntimeError("sampling did not return HTTP 200 GeoJSON")
        features = json.loads(result)["features"]
        if len(features) != count or any(feature["properties"]["value"] != expected for feature in features):
            raise RuntimeError("sampling did not read the supplied points' pixel values")
        print(f"PASS {locations['type']} input returns the supplied raster's values as GeoJSON")

    classes = [{"min": lower, "max": upper, "value": 1}]
    status, headers, classified = _read(
        f"{base_url.rstrip('/')}/processes/raster-reclassify/execution",
        {"inputs": {"source": source, "classes": classes}},
    )
    if status != 200 or headers.get_content_type() != "image/tiff":
        raise RuntimeError("reclassification did not return HTTP 200 TIFF")
    with MemoryFile(classified) as memory, memory.open() as raster:
        if (
            raster.count != 1
            or raster.dtypes != ("int32",)
            or not np.all(raster.read(1, masked=True).compressed() == 1)
        ):
            raise RuntimeError("reclassification output has incorrect classes or metadata")
    print("PASS reclassification returns one integer class on the source grid")
    if not polygon_supported:
        print("SKIP polygonization: supplied raster exceeds its 65,536 pixel bound")
        return
    classified_source = {
        "value": base64.b64encode(classified).decode("ascii"),
        "mediaType": "image/tiff",
        "encoding": "base64",
    }
    status, headers, result = _read(
        f"{base_url.rstrip('/')}/processes/raster-polygonize/execution",
        {
            "inputs": {"source": classified_source},
            "response": "document",
            "outputs": {"result": {"transmissionMode": "reference"}},
        },
    )
    if status != 200:
        raise RuntimeError("polygonization did not return HTTP 200")
    reference = json.loads(result)["result"]
    result_url = reference["href"]
    parsed = urlsplit(result_url)
    if parsed.scheme not in {"http", "https"} or reference["type"] != "application/geo+json":
        raise RuntimeError("polygonization did not advertise a GeoJSON download")
    status, headers, result = _read(result_url)
    collection = json.loads(result)
    if status != 200 or headers.get_content_type() != "application/geo+json" or not collection["features"]:
        raise RuntimeError("polygonization did not deliver a nonempty GeoJSON result")
    if any(feature["properties"]["value"] != 1 for feature in collection["features"]):
        raise RuntimeError("polygonization did not preserve the reclassified value")
    print("PASS reclassified raster polygonizes into independently downloadable WGS84 GeoJSON")


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
