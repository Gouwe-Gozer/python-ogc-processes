"""Shared raster request fixture and OpenAPI byte-format checking for tests."""

import base64
import binascii

from jsonschema import FormatChecker

from geo_processes.datasets import demo_source

DEMO_SOURCE = demo_source()
FORMATS = FormatChecker()


@FORMATS.checks("byte", raises=(ValueError, binascii.Error))
def is_base64(value):
    if isinstance(value, str):
        base64.b64decode(value, validate=True)
    return True
