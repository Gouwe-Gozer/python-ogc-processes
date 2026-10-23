"""Contract verified against Terrio 0.4.2's raster information response."""

from terrio_processes import __version__
from terrio_processes.datasets import DATASETS


def _numbers(length):
    return {"type": "array", "items": {"type": "number"}, "minItems": length, "maxItems": length}


INFO_SCHEMA = {
    "type": "object",
    "required": ["type", "driver", "size", "band_count", "geo_transform", "crs", "extent", "bands", "metadata"],
    "properties": {
        "type": {"type": "string", "enum": ["raster"]},
        "driver": {"type": "string"},
        "size": {"type": "array", "items": {"type": "integer", "minimum": 1}, "minItems": 2, "maxItems": 2},
        "band_count": {"type": "integer", "minimum": 1},
        "geo_transform": _numbers(6),
        "crs": {
            "type": "object",
            "required": ["epsg", "name", "wkt"],
            "properties": {"epsg": {"type": "integer"}, "name": {"type": "string"}, "wkt": {"type": "string"}},
            "additionalProperties": False,
        },
        "extent": _numbers(4),
        "wgs84_extent": _numbers(4),
        "bands": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["band", "data_type", "nodata", "statistics"],
                "properties": {
                    "band": {"type": "integer", "minimum": 1},
                    "data_type": {"type": "string"},
                    "nodata": {"type": "number"},
                    "statistics": {
                        "type": "object",
                        "required": ["min", "max", "mean", "std_dev", "valid_count"],
                        "properties": {
                            "min": {"type": "number"},
                            "max": {"type": "number"},
                            "mean": {"type": "number"},
                            "std_dev": {"type": "number", "minimum": 0},
                            "valid_count": {"type": "integer", "minimum": 0},
                        },
                        "additionalProperties": False,
                    },
                },
                "additionalProperties": False,
            },
        },
        "metadata": {"type": "array", "items": {}},
    },
    "additionalProperties": False,
}

PROCESS_METADATA = {
    "version": __version__,
    "id": "terrio-info",
    "title": "Terrio raster information",
    "description": "Inspect a bundled, bounded GeoTIFF using Terrio, including exact band statistics.",
    "keywords": ["Terrio", "raster", "GeoTIFF", "statistics"],
    "jobControlOptions": ["sync-execute"],
    "outputTransmission": ["value"],
    "links": [{"href": "https://terrio.opengeos.org/python/", "rel": "about", "type": "text/html"}],
    "inputs": {
        "source": {
            "title": "Dataset identifier",
            "description": "Inline identifier of a bundled raster. demo-dem is a 4 by 3 Float32 DEM in EPSG:28992.",
            "schema": {"type": "string", "enum": list(DATASETS)},
            "minOccurs": 1,
            "maxOccurs": 1,
        }
    },
    "outputs": {
        "info": {
            "title": "Raster information",
            "description": "Terrio raster metadata, georeferencing and exact band statistics as JSON.",
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
            "properties": {"source": PROCESS_METADATA["inputs"]["source"]["schema"]},
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
