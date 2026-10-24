"""Rasterio-backed OGC API Processes service."""

import os

# Set before importing pygeoapi/Rasterio and creating PROJ contexts. Remote
# raster access belongs to our validated input resolver, including redirects.
os.environ["PROJ_NETWORK"] = "OFF"

__version__ = "0.1.0"
