"""Apply explicit half-open class intervals using bounded NumPy comparisons."""

import numpy as np
import rasterio

from geo_processes.engine import GDAL_OPTIONS

NODATA = -2147483648


def reclassify(source, destination, classes, band):
    with rasterio.Env(**GDAL_OPTIONS), rasterio.open(source, driver="GTiff", GEOREF_SOURCES="INTERNAL") as raster:
        values = raster.read(band, masked=True)
        valid = ~np.ma.getmaskarray(values) & np.isfinite(values.data)
        result = np.full(values.shape, NODATA, dtype="int32")
        for item in classes:
            selected = valid & (values.data >= item["min"]) & (values.data < item["max"])
            result[selected] = item["value"]
        with rasterio.open(
            destination,
            "w",
            driver="GTiff",
            width=raster.width,
            height=raster.height,
            count=1,
            dtype="int32",
            crs=raster.crs,
            transform=raster.transform,
            nodata=NODATA,
            compress="deflate",
        ) as output:
            output.write(result, 1)
