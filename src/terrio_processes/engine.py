"""Small Terrio adapter, independent of the HTTP and OGC layers."""

import json
from pathlib import Path

import terrio


class RasterInfoError(RuntimeError):
    """The configured raster could not be inspected."""


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
