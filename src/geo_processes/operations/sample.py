"""Sample one band at WGS84 point locations using Rasterio's pixel sampler."""

from copy import deepcopy

import numpy as np
import rasterio
from rasterio.warp import transform

from geo_processes.engine import GDAL_OPTIONS
from geo_processes.operations.vector import write_features


def sample_points(source, destination, points, band):
    with rasterio.Env(**GDAL_OPTIONS), rasterio.open(source, driver="GTiff", GEOREF_SOURCES="INTERNAL") as raster:
        coordinates = [feature["geometry"]["coordinates"] for feature in points["features"]]
        xs, ys = transform("EPSG:4326", raster.crs, [p[0] for p in coordinates], [p[1] for p in coordinates])

        def features():
            for feature, values in zip(
                points["features"], raster.sample(zip(xs, ys, strict=True), indexes=band, masked=True), strict=True
            ):
                value = values[0]
                result = deepcopy(feature)
                result["properties"] = dict(result.get("properties") or {})
                result["properties"]["value"] = (
                    None if np.ma.is_masked(value) or not np.isfinite(value) else value.item()
                )
                yield result

        write_features(destination, features())
