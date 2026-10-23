"""Bounded Rasterio operations, independent of the HTTP and OGC layers."""

import json
import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject, transform_bounds

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_SAMPLES = 1024 * 1024


class RasterInfoError(RuntimeError):
    """The configured raster could not be inspected."""


class RasterWarpError(RuntimeError):
    """The approved raster could not be reprojected within its bounds."""


def _check_bounds(source: Path, raster) -> None:
    if source.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("source exceeds the byte limit")
    if raster.width * raster.height * raster.count > MAX_SAMPLES:
        raise ValueError("source exceeds the sample limit")
    if any(np.issubdtype(np.dtype(dtype), np.complexfloating) for dtype in raster.dtypes):
        raise ValueError("complex rasters are not supported")


def _nodata(value):
    if value is None or math.isfinite(value):
        return value
    if math.isnan(value):
        return "NaN"
    return "Infinity" if value > 0 else "-Infinity"


def raster_info(source: Path) -> dict:
    """Return application-owned metadata and exact masked, finite statistics."""
    try:
        if source.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("source exceeds the byte limit")
        with rasterio.open(source) as raster:
            _check_bounds(source, raster)
            crs = raster.crs
            bands = []
            for index in raster.indexes:
                values = np.ma.masked_invalid(raster.read(index, masked=True).astype("float64"))
                count = int(values.count())
                bands.append(
                    {
                        "band": index,
                        "data_type": raster.dtypes[index - 1],
                        "nodata": _nodata(raster.nodatavals[index - 1]),
                        "statistics": {
                            "min": float(values.min()) if count else None,
                            "max": float(values.max()) if count else None,
                            "mean": float(values.mean()) if count else None,
                            "std_dev": float(values.std()) if count else None,
                            "valid_count": count,
                        },
                    }
                )
            result = {
                "type": "raster",
                "driver": raster.driver,
                "size": [raster.width, raster.height],
                "band_count": raster.count,
                "geo_transform": list(raster.transform.to_gdal()),
                "crs": {"epsg": crs.to_epsg(), "wkt": crs.to_wkt()} if crs else None,
                "extent": list(raster.bounds),
                "wgs84_extent": list(transform_bounds(crs, "EPSG:4326", *raster.bounds)) if crs else None,
                "bands": bands,
                "metadata": raster.tags(),
            }
        json.dumps(result, allow_nan=False)
    except Exception as error:
        raise RasterInfoError("configured raster could not be inspected") from error
    return result


def warp_raster(source: Path, destination: Path, target_crs: str, resampling: str) -> None:
    """Reproject each band to a GeoTIFF while retaining bounded dimensions."""
    try:
        if source.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("source exceeds the byte limit")
        with rasterio.open(source) as raster:
            _check_bounds(source, raster)
            if raster.crs is None:
                raise ValueError("source CRS is required for reprojection")
            transform, width, height = calculate_default_transform(
                raster.crs,
                target_crs,
                raster.width,
                raster.height,
                *raster.bounds,
                dst_width=raster.width,
                dst_height=raster.height,
            )
            profile = raster.profile.copy()
            profile.update(driver="GTiff", crs=target_crs, transform=transform, width=width, height=height)
            with rasterio.open(destination, "w", **profile) as output:
                for index in raster.indexes:
                    reproject(
                        source=rasterio.band(raster, index),
                        destination=rasterio.band(output, index),
                        src_transform=raster.transform,
                        src_crs=raster.crs,
                        src_nodata=raster.nodatavals[index - 1],
                        dst_transform=transform,
                        dst_crs=target_crs,
                        dst_nodata=raster.nodatavals[index - 1],
                        resampling=Resampling[resampling],
                        num_threads=1,
                        warp_mem_limit=64,
                    )
    except Exception as error:
        raise RasterWarpError("configured raster could not be reprojected") from error
