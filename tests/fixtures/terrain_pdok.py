"""Deterministic PDOK responses shared by unit and actual-worker tests only."""

import json

import requests


def features_by_collection():
    from pyproj import Transformer
    from shapely.geometry import box, mapping
    from shapely.ops import transform

    to_rd = Transformer.from_crs(4326, 28992, always_xy=True).transform
    to_wgs = Transformer.from_crs(28992, 4326, always_xy=True).transform
    x, y = to_rd(4.75, 52.63)

    def feature(identifier, bounds, physical=""):
        a, b, c, d = bounds
        return {
            "type": "Feature",
            "id": identifier,
            "geometry": mapping(transform(to_wgs, box(x + a, y + b, x + c, y + d))),
            "properties": {"fysiek_voorkomen": physical},
        }

    return {
        "begroeidterreindeel": [
            feature("grass", (-100, -100, 100, 100), "grasland overig"),
            feature("trees", (-100, 50, -50, 100), "loofbos"),
            feature("shrubs", (-50, 50, 0, 100), "struiken"),
        ],
        "onbegroeidterreindeel": [
            feature("built", (50, -50, 100, 0), "verhard"),
            feature("sand", (110, 110, 150, 150), "zand"),
        ],
        "waterdeel": [feature("water", (-150, -150, -110, -110))],
        "wegdeel": [feature("road", (-50, -50, 0, 50))],
        "pand": [feature("building", (0, 0, 50, 50))],
    }


def fake_pdok_get(url, *, params, timeout):
    assert url.startswith("https://api.pdok.nl/lv/bgt/ogc/v1/collections/")
    assert timeout == 30 and params["f"] == "json"
    collection = url.split("/")[-2]
    response = requests.Response()
    response.status_code = 200
    response.url = url
    response._content = json.dumps(
        {"type": "FeatureCollection", "features": features_by_collection()[collection]}
    ).encode()
    response.headers["Content-Type"] = "application/geo+json"
    return response
