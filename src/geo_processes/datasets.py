"""Packaged raster fixtures and the public sample-data directory."""

import base64
import os
from pathlib import Path

DEMO_RASTER = Path(__file__).resolve().parent / "data" / "demo-dem.tif"
SAMPLE_DATA_DIR = Path(os.environ.get("GEO_SAMPLE_DATA_DIR", str(DEMO_RASTER.parent / "samples"))).resolve()


def demo_source():
    """Submit the fixture through the same qualified input contract as user data."""
    return {
        "value": base64.b64encode(DEMO_RASTER.read_bytes()).decode("ascii"),
        "mediaType": "image/tiff",
        "encoding": "base64",
    }
