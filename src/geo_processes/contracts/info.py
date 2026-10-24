"""Application-owned raster metadata contract, independent of the library API."""

from geo_processes import __version__
from geo_processes.contracts.sources import SOURCE_DESCRIPTION, SOURCE_EXECUTE_SCHEMA, SOURCE_VALUE_SCHEMA
from geo_processes.datasets import DATASETS as DATASETS


def _numbers(length):
    return {"type": "array", "items": {"type": "number"}, "minItems": length, "maxItems": length}


def _nullable(schema):
    # enum:null works in JSON Schema and avoids OpenAPI 3.0's unsupported type:null.
    return {"anyOf": [schema, {"enum": [None]}]}


INFO_SCHEMA = {
    "type": "object",
    "required": ["type", "driver", "size", "band_count", "geo_transform", "crs", "extent", "bands", "metadata"],
    "properties": {
        "type": {"type": "string", "enum": ["raster"]},
        "driver": {"type": "string"},
        "size": {"type": "array", "items": {"type": "integer", "minimum": 1}, "minItems": 2, "maxItems": 2},
        "band_count": {"type": "integer", "minimum": 1},
        "geo_transform": _numbers(6),
        "crs": _nullable(
            {
                "type": "object",
                "required": ["epsg", "wkt"],
                "properties": {"epsg": _nullable({"type": "integer"}), "wkt": {"type": "string"}},
                "additionalProperties": False,
            }
        ),
        "extent": _numbers(4),
        "wgs84_extent": _nullable(_numbers(4)),
        "bands": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["band", "data_type", "nodata", "statistics"],
                "properties": {
                    "band": {"type": "integer", "minimum": 1},
                    "data_type": {"type": "string"},
                    "nodata": {"anyOf": [_nullable({"type": "number"}), {"enum": ["NaN", "Infinity", "-Infinity"]}]},
                    "statistics": {
                        "type": "object",
                        "required": ["min", "max", "mean", "std_dev", "valid_count"],
                        "properties": {
                            "min": _nullable({"type": "number"}),
                            "max": _nullable({"type": "number"}),
                            "mean": _nullable({"type": "number"}),
                            "std_dev": _nullable({"type": "number", "minimum": 0}),
                            "valid_count": {"type": "integer", "minimum": 0},
                        },
                        "additionalProperties": False,
                    },
                },
                "additionalProperties": False,
            },
        },
        "metadata": {"type": "object", "additionalProperties": {"type": "string"}},
    },
    "additionalProperties": False,
}

PROCESS_METADATA = {
    "version": __version__,
    "id": "raster-info",
    "title": "Raster information",
    "description": (
        "Inspect a bounded GeoTIFF supplied by the user or the bundled demo, including exact finite statistics."
    ),
    "keywords": ["Rasterio", "raster", "GeoTIFF", "statistics"],
    "jobControlOptions": ["sync-execute"],
    "outputTransmission": ["value"],
    "links": [{"href": "https://rasterio.readthedocs.io/en/stable/", "rel": "about", "type": "text/html"}],
    "inputs": {
        "source": {
            "title": "Source GeoTIFF",
            "description": SOURCE_DESCRIPTION,
            "schema": SOURCE_VALUE_SCHEMA,
            "minOccurs": 1,
            "maxOccurs": 1,
        }
    },
    "outputs": {
        "info": {
            "title": "Raster information",
            "description": (
                "Application-defined raster metadata, georeferencing and exact finite band statistics as JSON."
            ),
            "schema": {"contentMediaType": "application/json", **INFO_SCHEMA},
        }
    },
    "example": {"inputs": {"source": "demo-dem"}},
}

EXECUTE_SCHEMA = {
    "type": "object",
    "required": ["inputs"],
    "properties": {
        "inputs": {
            "type": "object",
            "required": ["source"],
            "properties": {"source": SOURCE_EXECUTE_SCHEMA},
            "additionalProperties": False,
        },
        "outputs": {
            "type": "object",
            "minProperties": 1,
            "properties": {
                "info": {
                    "type": "object",
                    "properties": {
                        "transmissionMode": {"type": "string", "enum": ["value"], "default": "value"},
                        "format": {
                            "type": "object",
                            "properties": {
                                "mediaType": {
                                    "type": "string",
                                    "enum": ["application/json"],
                                    "default": "application/json",
                                }
                            },
                            "additionalProperties": False,
                        },
                    },
                    "additionalProperties": False,
                }
            },
            "additionalProperties": False,
        },
        "response": {"type": "string", "enum": ["raw", "document"], "default": "raw"},
    },
    "additionalProperties": False,
}

DOCUMENT_SCHEMA = {
    "type": "object",
    "required": ["info"],
    "properties": {
        "info": {
            "type": "object",
            "required": ["value"],
            "properties": {"value": INFO_SCHEMA},
            "additionalProperties": False,
        }
    },
    "additionalProperties": False,
}
