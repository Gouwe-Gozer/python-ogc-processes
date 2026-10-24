"""Bundled raster fixture for tests and smoke clients, without an API identifier."""

import base64
from pathlib import Path

DEMO_RASTER = Path(__file__).resolve().parent / "data" / "demo-dem.tif"


def demo_source():
    """Submit the fixture through the same qualified input contract as user data."""
    return {
        "value": base64.b64encode(DEMO_RASTER.read_bytes()).decode("ascii"),
        "mediaType": "image/tiff",
        "encoding": "base64",
    }
