"""The bounded GeoTIFF reprojection contract and its HTTP representations."""

from geo_processes import __version__
from geo_processes.contracts.sources import SOURCE_DESCRIPTION, SOURCE_EXECUTE_SCHEMA, SOURCE_VALUE_SCHEMA

TARGET_CRSS = ["EPSG:28992", "EPSG:4326", "EPSG:3857"]
RESAMPLING_METHODS = ["nearest", "bilinear"]
TIFF_TYPE = "image/tiff"

INPUTS_SCHEMA = {
    "type": "object",
    "required": ["source", "target_crs"],
    "properties": {
        "source": SOURCE_EXECUTE_SCHEMA,
        "target_crs": {"type": "string", "enum": TARGET_CRSS},
        "resampling": {"type": "string", "enum": RESAMPLING_METHODS, "default": "bilinear"},
    },
    "additionalProperties": False,
}
EXECUTE_SCHEMA = {
    "type": "object",
    "required": ["inputs"],
    "properties": {
        "inputs": INPUTS_SCHEMA,
        "response": {"type": "string", "enum": ["raw", "document"], "default": "raw"},
        "outputs": {
            "type": "object",
            "minProperties": 1,
            "properties": {
                "result": {
                    "type": "object",
                    "properties": {
                        "transmissionMode": {"type": "string", "enum": ["value", "reference"], "default": "value"},
                        "format": {
                            "type": "object",
                            "properties": {"mediaType": {"type": "string", "enum": [TIFF_TYPE], "default": TIFF_TYPE}},
                            "additionalProperties": False,
                        },
                    },
                    "additionalProperties": False,
                }
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}
REFERENCE_SCHEMA = {
    "type": "object",
    "required": ["href", "type"],
    "properties": {"href": {"type": "string", "format": "uri"}, "type": {"type": "string", "enum": [TIFF_TYPE]}},
    "additionalProperties": False,
}
INLINE_SCHEMA = {
    "type": "object",
    "required": ["value", "mediaType", "encoding"],
    "properties": {
        "value": {"type": "string", "format": "byte"},
        "mediaType": {"type": "string", "enum": [TIFF_TYPE]},
        "encoding": {"type": "string", "enum": ["base64"]},
    },
    "additionalProperties": False,
}
DOCUMENT_SCHEMA = {
    "type": "object",
    "required": ["result"],
    "properties": {"result": {"oneOf": [REFERENCE_SCHEMA, INLINE_SCHEMA]}},
    "additionalProperties": False,
}
PROCESS_METADATA = {
    "id": "raster-warp",
    "version": __version__,
    "title": "Raster reprojection",
    "description": (
        "Reproject a bounded user-supplied GeoTIFF, retaining its grid dimensions. "
        "Raw/value returns TIFF bytes; document/value returns base64. Explicit reference transmission "
        "returns a download URL (document) or HTTP 204 with a Link header (raw). "
        "Results are retained for 24 hours by default, subject to configured storage limits."
    ),
    "keywords": ["Rasterio", "GeoTIFF", "reprojection"],
    "jobControlOptions": ["sync-execute"],
    "outputTransmission": ["value", "reference"],
    "inputs": {
        "source": {
            "title": "Source GeoTIFF",
            "description": SOURCE_DESCRIPTION,
            "schema": SOURCE_VALUE_SCHEMA,
            "minOccurs": 1,
            "maxOccurs": 1,
        },
        "target_crs": {
            "title": "Target CRS",
            "description": "Target EPSG identifier. Resolution follows the transformed extent and retained grid size.",
            "schema": INPUTS_SCHEMA["properties"]["target_crs"],
            "minOccurs": 1,
            "maxOccurs": 1,
        },
        "resampling": {
            "title": "Resampling method",
            "schema": INPUTS_SCHEMA["properties"]["resampling"],
            "minOccurs": 0,
            "maxOccurs": 1,
        },
    },
    "outputs": {
        "result": {
            "title": "Reprojected GeoTIFF",
            "description": "GeoTIFF by value or a retrievable HTTP reference. Downloads expire with the stored result.",
            "schema": {"type": "string", "format": "binary", "contentMediaType": TIFF_TYPE},
        }
    },
    "example": {
        "inputs": {
            "source": {"href": "https://data.example.org/dem.tif", "type": "image/tiff"},
            "target_crs": "EPSG:4326",
        }
    },
}
