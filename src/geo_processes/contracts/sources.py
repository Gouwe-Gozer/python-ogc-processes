"""Raster value semantics and the separate supported OGC wire representations."""

from geo_processes.inputs import LINK_METADATA, MAX_ENCODED_BYTES, MAX_URL_LENGTH, MEDIA_TYPES, SCALAR_MEDIA_TYPES

SOURCE_VALUE_SCHEMA = {
    "type": "string",
    "format": "byte",
    "contentEncoding": "binary",
    "contentMediaType": "image/tiff",
}
BASE64_SCHEMA = {"type": "string", "format": "byte", "maxLength": MAX_ENCODED_BYTES}
REFERENCE_SCHEMA = {
    "type": "object",
    "required": ["href"],
    "properties": {
        "href": {"type": "string", "format": "uri", "pattern": "^https://", "maxLength": MAX_URL_LENGTH},
        "type": {"type": "string", "enum": list(MEDIA_TYPES)},
        **{key: {"type": "string"} for key in sorted(LINK_METADATA)},
    },
    "additionalProperties": False,
}
INLINE_SCHEMA = {
    "type": "object",
    "required": ["value", "mediaType", "encoding"],
    "properties": {
        "value": BASE64_SCHEMA,
        "mediaType": {"type": "string", "enum": list(MEDIA_TYPES)},
        "encoding": {"type": "string", "enum": ["base64"]},
    },
    "additionalProperties": False,
}
SOURCE_EXECUTE_SCHEMA = {"oneOf": [BASE64_SCHEMA, REFERENCE_SCHEMA, INLINE_SCHEMA]}
SOURCE_DESCRIPTION = (
    "A self-contained GeoTIFF (image/tiff; application/tiff and application/tiff; application=geotiff "
    "are accepted aliases). Supply an HTTPS href, an inline base64 string or a qualified base64 value. "
    "Inputs are limited to 16 MiB and 1,048,576 samples including bands. "
    "HTTPS uses port 443 and public destinations only; files are discarded after execution."
)


def scalar_execution_schema(value_schema):
    """Wire forms belong to execution, not the process's scalar value schema."""
    return {
        "oneOf": [
            value_schema,
            {
                "type": "object",
                "required": ["href"],
                "properties": {
                    "href": {"type": "string", "format": "uri", "pattern": "^https://", "maxLength": MAX_URL_LENGTH},
                    "type": {"type": "string", "enum": list(SCALAR_MEDIA_TYPES)},
                    **{key: {"type": "string"} for key in sorted(LINK_METADATA)},
                },
                "additionalProperties": False,
            },
            {
                "type": "object",
                "required": ["value"],
                "properties": {
                    "value": value_schema,
                    "mediaType": {"type": "string", "enum": list(SCALAR_MEDIA_TYPES)},
                },
                "additionalProperties": False,
            },
        ]
    }
