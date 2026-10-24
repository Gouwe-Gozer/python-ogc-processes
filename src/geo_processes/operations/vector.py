"""Bounded GeoJSON serialization shared by the two vector-producing adapters."""

import json
import math

from geo_processes.engine import RasterValidationError

MAX_VECTOR_BYTES = 16 * 1024 * 1024


def polygon_geometry(geometry):
    """Apply RFC 7946 ring winding to GDAL's polygon coordinates.

    This is serialization only: GDAL still constructs and reprojects every
    polygon. Reject coordinates outside GeoJSON's geographic domain.
    """
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    for polygon in polygons:
        for index, ring in enumerate(polygon):
            if any(
                not math.isfinite(x) or not math.isfinite(y) or not -180 <= x <= 180 or not -90 <= y <= 90
                for x, y in ring
            ):
                raise RasterValidationError("source cannot be represented as WGS84 GeoJSON")
            area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:], strict=False))
            if (area > 0) != (index == 0):
                ring.reverse()
    return geometry


def write_features(destination, features):
    encoder = json.JSONEncoder(allow_nan=False, separators=(",", ":"))
    size = 0
    with destination.open("wb") as output:

        def write(text):
            nonlocal size
            data = text.encode("utf-8")
            size += len(data)
            if size > MAX_VECTOR_BYTES:
                raise RasterValidationError("GeoJSON output exceeds 16 MiB; use a smaller input")
            output.write(data)

        write('{"type":"FeatureCollection","features":[')
        for index, feature in enumerate(features):
            if index:
                write(",")
            for chunk in encoder.iterencode(feature):
                write(chunk)
        write("]}")
