"""Extract categorical regions with GDAL via rasterio.features.shapes."""

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform_geom

from geo_processes.engine import GDAL_OPTIONS, RasterValidationError
from geo_processes.operations.vector import polygon_geometry, write_features

MAX_POLYGON_PIXELS = 65536
MAX_FEATURES = 4096
POLYGON_DTYPES = {"int8", "uint8", "int16", "uint16", "int32"}


def polygonize(source, destination, band, connectivity):
    with rasterio.Env(**GDAL_OPTIONS), rasterio.open(source, driver="GTiff", GEOREF_SOURCES="INTERNAL") as raster:
        if raster.width * raster.height > MAX_POLYGON_PIXELS:
            raise RasterValidationError("polygonize accepts at most 65,536 pixels; use a smaller categorical raster")
        if raster.dtypes[band - 1] not in POLYGON_DTYPES:
            raise RasterValidationError("polygonize requires an int8/uint8/int16/uint16/int32 categorical band")
        values = raster.read(band, masked=True)
        image = values.data.astype("int16") if values.dtype == np.dtype("int8") else values.data

        regions = []
        for region in shapes(
            image, mask=~np.ma.getmaskarray(values), transform=raster.transform, connectivity=connectivity
        ):
            if len(regions) >= MAX_FEATURES:
                raise RasterValidationError("polygonize exceeds 4,096 features; reclassify or use a smaller raster")
            regions.append(region)
        # One GDAL transformation avoids repeating CRS/grid setup per polygon.
        # Both the input pixel budget and feature cap bound this collection.
        geometries = (
            transform_geom(
                raster.crs,
                "EPSG:4326",
                {"type": "GeometryCollection", "geometries": [geometry for geometry, _value in regions]},
            )["geometries"]
            if regions
            else []
        )

        def features():
            for index, (geometry, (_original, value)) in enumerate(zip(geometries, regions, strict=True)):
                yield {
                    "type": "Feature",
                    "id": index + 1,
                    "geometry": polygon_geometry(geometry),
                    "properties": {"value": int(value)},
                }

        write_features(destination, features())
