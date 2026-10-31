"""Convert stored pixel values with explicit overflow, rounding and nodata policy."""

import math

import numpy as np
import rasterio
from rasterio.enums import ColorInterp

from geo_processes.engine import GDAL_OPTIONS

DTYPES = ("uint8", "uint16", "int16", "float32", "float64")


def convert_dtype(source, destination, dtype, *, overflow="error", rounding="truncate", nodata=None):
    """Convert every band; preserve grid, descriptive metadata and validity.

    No scale/offset is applied to stored pixels. Integer rounding is truncation
    toward zero or nearest with ties to even. Nonfinite valid pixels and nodata
    collisions are errors. An unrepresentable source nodata or a mask without a
    sentinel requires explicit destination nodata. Different band masks remain
    different through the shared GeoTIFF nodata sentinel.
    """
    if dtype not in DTYPES or overflow not in {"error", "clip"} or rounding not in {"truncate", "nearest"}:
        raise ValueError("unsupported dtype, overflow or rounding policy")
    target = np.dtype(dtype)
    integer = np.issubdtype(target, np.integer)
    bounds = np.iinfo(target) if integer else np.finfo(target)

    def sentinel(value):
        if value is None:
            return None
        if not math.isfinite(value):
            if not integer and math.isnan(value):
                return value
            raise ValueError("nodata is not representable; supply finite destination nodata")
        if not bounds.min <= value <= bounds.max or (integer and value != math.trunc(value)):
            raise ValueError("nodata is not representable; supply destination nodata")
        converted = target.type(value).item()
        if converted != value:
            raise ValueError("nodata must be exactly representable in the destination dtype")
        return converted

    with rasterio.Env(**GDAL_OPTIONS), rasterio.open(source, driver="GTiff", GEOREF_SOURCES="INTERNAL") as raster:
        if ColorInterp.palette in raster.colorinterp or raster.gcps[0] or raster.tags(ns="RPC"):
            raise ValueError("palette and GCP/RPC rasters are unsupported by this conversion")
        output_nodata = sentinel(raster.nodata if nodata is None else nodata)
        arrays = []
        for band in range(1, raster.count + 1):
            pixels = raster.read(band, masked=True)
            mask = np.ma.getmaskarray(pixels)
            if mask.any() and output_nodata is None:
                raise ValueError("masked source pixels require explicit destination nodata")
            values = pixels.data[~mask].astype("float64")
            if not np.isfinite(values).all():
                raise ValueError("nonfinite valid pixels cannot be converted; declare source nodata")
            if integer:
                values = np.trunc(values) if rounding == "truncate" else np.rint(values)
            outside = (values < bounds.min) | (values > bounds.max)
            if outside.any() and overflow == "error":
                raise ValueError("pixels overflow the destination dtype; choose overflow=clip explicitly")
            converted = np.clip(values, bounds.min, bounds.max).astype(target)
            if output_nodata is not None and (converted == output_nodata).any():
                raise ValueError("destination nodata collides with a converted valid pixel")
            output = np.full(pixels.shape, output_nodata if output_nodata is not None else 0, dtype=target)
            output[~mask] = converted
            arrays.append(output)

        # Rebuild the profile: source predictors/photometric options may be
        # incompatible with another dtype. Compression/layout are not semantics.
        with rasterio.open(
            destination,
            "w",
            driver="GTiff",
            width=raster.width,
            height=raster.height,
            count=raster.count,
            dtype=dtype,
            crs=raster.crs,
            transform=raster.transform,
            nodata=output_nodata,
            compress="deflate",
        ) as output:
            for band, values in enumerate(arrays, 1):
                output.write(values, band)
            output.scales = raster.scales
            output.offsets = raster.offsets
            output.colorinterp = raster.colorinterp
            for band in range(raster.count + 1):
                # Statistics describe source pixels and must be recomputed.
                tags = {k: v for k, v in raster.tags(band).items() if not k.startswith("STATISTICS_")}
                output.update_tags(band, **tags)
                if band:
                    if raster.descriptions[band - 1]:
                        output.set_band_description(band, raster.descriptions[band - 1])
                    if raster.units[band - 1]:
                        output.set_band_unit(band, raster.units[band - 1])
