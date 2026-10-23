"""Small Terrio adapter, independent of the HTTP and OGC layers."""

import json
from pathlib import Path

import terrio

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_SAMPLES = 1024 * 1024


class RasterInfoError(RuntimeError):
    """The configured raster could not be inspected."""


class RasterWarpError(RuntimeError):
    """The approved raster could not be reprojected within its bounds."""


def raster_info(source: Path) -> dict:
    """Inspect a trusted local raster with the pinned Terrio Python binding."""
    try:
        result = terrio.info(str(source), stats=True)
        if not isinstance(result, dict) or result.get("type") != "raster":
            raise ValueError("expected raster information")
        # Reject non-finite values and other non-JSON results before HTTP encoding.
        json.dumps(result, allow_nan=False)
    except Exception as error:
        raise RasterInfoError("configured raster could not be inspected") from error
    return result


def warp_raster(source: Path, destination: Path, target_crs: str, resampling: str) -> None:
    """Write a GeoTIFF while retaining the source's bounded grid dimensions."""
    try:
        if source.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("source exceeds the byte limit")
        raster = terrio.open_raster(str(source), lazy=True)
        if raster.width * raster.height * raster.count > MAX_SAMPLES:
            raise ValueError("source exceeds the sample limit")
        terrio.warp(
            str(source),
            str(destination),
            t_srs=target_crs,
            resampling="near" if resampling == "nearest" else resampling,
            ts=(raster.width, raster.height),
            format="GTiff",
            et=0,
        )
    except Exception as error:
        raise RasterWarpError("configured raster could not be reprojected") from error
