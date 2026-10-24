"""Raster value semantics and the separate supported OGC wire representations."""

from geo_processes.datasets import DATASETS
from geo_processes.inputs import MAX_ENCODED_BYTES, MAX_URL_LENGTH, MEDIA_TYPES

DEMO_SCHEMA = {"type": "string", "enum": list(DATASETS)}
SOURCE_VALUE_SCHEMA = {"anyOf": [DEMO_SCHEMA, {"type": "string", "format": "binary", "contentMediaType": "image/tiff"}]}
REFERENCE_SCHEMA = {
    "type": "object",
    "required": ["href"],
    "properties": {
        "href": {"type": "string", "format": "uri", "pattern": "^https://", "maxLength": MAX_URL_LENGTH},
        "type": {"type": "string", "enum": list(MEDIA_TYPES)},
    },
    "additionalProperties": False,
}
INLINE_SCHEMA = {
    "type": "object",
    "required": ["value", "mediaType", "encoding"],
    "properties": {
        "value": {"type": "string", "format": "byte", "maxLength": MAX_ENCODED_BYTES},
        "mediaType": {"type": "string", "enum": list(MEDIA_TYPES)},
        "encoding": {"type": "string", "enum": ["base64"]},
    },
    "additionalProperties": False,
}
SOURCE_EXECUTE_SCHEMA = {"oneOf": [DEMO_SCHEMA, REFERENCE_SCHEMA, INLINE_SCHEMA]}
SOURCE_DESCRIPTION = (
    "A self-contained GeoTIFF supplied as an HTTPS href or qualified base64 value, "
    "or the bundled demo-dem identifier. Inputs are limited to 16 MiB and 1,048,576 samples including bands. "
    "HTTPS uses port 443 and public destinations only; files are discarded after execution."
)
