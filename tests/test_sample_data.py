"""Publish the user's sample data through native pygeoapi Features routes."""

import base64
import hashlib
import json
import logging
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
import pytest
import yaml
from jsonschema import Draft4Validator
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from rasterio.warp import transform, transform_geom
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4

BASE = "https://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/schemas/"
ROOT = Path(__file__).parent / "schemas" / "ogc-features-1.0"
REGISTRY = Registry().with_resources(
    (BASE + path.name, Resource.from_contents(yaml.safe_load(path.read_text()), default_specification=DRAFT4))
    for path in ROOT.glob("*.yaml")
)
RASTER = "AHN4_R5_117000_517000.TIF"
COORDINATES = [[4.836065, 52.647618], [4.827911, 52.645173], [4.834395, 52.644807]]


def validate(document, schema):
    Draft4Validator({"$ref": BASE + schema}, registry=REGISTRY).validate(document)


def test_collections_are_discoverable_and_link_the_matching_raster(http_client):
    response = http_client.get("/collections?f=json")
    assert response.status_code == 200
    document = response.get_json()
    validate(document, "collections.yaml")
    assert {collection["id"] for collection in document["collections"]} == {"sample-points", "sample-polygons"}
    for collection in document["collections"]:
        response = http_client.get(f"/collections/{collection['id']}?f=json")
        assert response.status_code == 200
        detail = response.get_json()
        validate(detail, "collection.yaml")
        assert detail["id"] == collection["id"] and detail["extent"] == collection["extent"]
        items = next(
            link for link in detail["links"] if link["rel"] == "items" and link["type"] == "application/geo+json"
        )
        assert http_client.get(urlsplit(items["href"]).path + "?f=json").status_code == 200
        raster = next(link for link in detail["links"] if link["type"] == "image/tiff")
        assert urlsplit(raster["href"]).path == f"/sample-data/{RASTER}"


def test_points_preserve_coordinates_properties_and_stable_item_ids(http_client):
    response = http_client.get("/collections/sample-points/items?f=json")
    assert response.status_code == 200 and response.mimetype == "application/geo+json"
    document = response.get_json()
    validate(document, "featureCollectionGeoJSON.yaml")
    assert document["numberMatched"] == document["numberReturned"] == 3
    assert [feature["geometry"]["coordinates"] for feature in document["features"]] == COORDINATES
    assert [feature["id"] for feature in document["features"]] == ["point-1", "point-2", "point-3"]
    assert all(feature["properties"] == {} for feature in document["features"])
    for feature in document["features"]:
        item = http_client.get(f"/collections/sample-points/items/{feature['id']}?f=json")
        assert item.status_code == 200 and item.mimetype == "application/geo+json"
        validate(item.get_json(), "featureGeoJSON.yaml")
        assert item.get_json()["id"] == feature["id"]
    assert http_client.get("/collections/sample-points/items/missing?f=json").status_code == 404


def test_native_features_paging_and_bbox_work(http_client):
    page = http_client.get("/collections/sample-points/items?f=json&limit=1").get_json()
    validate(page, "featureCollectionGeoJSON.yaml")
    assert page["numberMatched"] == 3 and page["numberReturned"] == 1
    next_link = next(link for link in page["links"] if link["rel"] == "next")
    target = urlsplit(next_link["href"])
    second = http_client.get(target.path + "?" + target.query).get_json()
    assert second["features"][0]["id"] != page["features"][0]["id"]
    selected = http_client.get("/collections/sample-points/items?f=json&bbox=4.835,52.647,4.837,52.649").get_json()
    assert [feature["id"] for feature in selected["features"]] == ["point-1"]


def test_published_raster_is_unchanged_and_polygon_is_inside_its_footprint(http_client):
    response = http_client.get(f"/sample-data/{RASTER}")
    assert response.status_code == 200 and response.mimetype == "image/tiff"
    assert (
        hashlib.sha256(response.data).hexdigest() == "7401de276a5f08f9fe3b6003d0860159e4544c348d0747f01a865a5dcdcf7f33"
    )
    polygons = http_client.get("/collections/sample-polygons/items?f=json").get_json()
    validate(polygons, "featureCollectionGeoJSON.yaml")
    assert len(polygons["features"]) == 1
    with MemoryFile(response.data) as memory, memory.open() as raster:
        assert (raster.width, raster.height, raster.count) == (200, 200, 1)
        assert raster.crs.to_epsg() == 7415
        geometry = transform_geom("EPSG:4326", raster.crs, polygons["features"][0]["geometry"])
        assert all(
            raster.bounds.left < x < raster.bounds.right and raster.bounds.bottom < y < raster.bounds.top
            for x, y in geometry["coordinates"][0]
        )
        xs, ys = transform(
            "EPSG:4326", raster.crs, [point[0] for point in COORDINATES], [point[1] for point in COORDINATES]
        )
        inside = geometry_mask([geometry], out_shape=raster.shape, transform=raster.transform, invert=True)
        assert inside.any()
        assert all(inside[raster.index(x, y)] for x, y in zip(xs, ys, strict=True))
        valid = raster.read(1, masked=True)
        assert all(not np.ma.is_masked(valid[raster.index(x, y)]) for x, y in zip(xs, ys, strict=True))


def test_features_response_can_be_submitted_directly_for_sampling(http_client):
    points = http_client.get("/collections/sample-points/items?f=json").get_json()
    raster = http_client.get(f"/sample-data/{RASTER}").data
    assert "links" in points and "numberMatched" in points
    response = http_client.post(
        "/processes/raster-sample-points/execution",
        json={
            "inputs": {
                "source": {"value": base64.b64encode(raster).decode(), "mediaType": "image/tiff", "encoding": "base64"},
                "points": {"value": points, "mediaType": "application/geo+json"},
            }
        },
    )
    assert response.status_code == 200
    sampled = json.loads(response.data)["features"]
    assert [feature["properties"]["value"] for feature in sampled] == pytest.approx([1.9285001, 3.2803838, -2.1010699])
    assert [feature["id"] for feature in sampled] == ["point-1", "point-2", "point-3"]


def test_sample_html_does_not_reintroduce_false_locale_warnings(http_client, monkeypatch, caplog):
    from pygeoapi import l10n

    monkeypatch.setattr(l10n, "_cfg_cache", {})
    with caplog.at_level(logging.WARNING, logger="pygeoapi.l10n"):
        for path in ("/?f=html", "/collections?f=html", "/collections/sample-points/items?f=html"):
            assert http_client.get(path).status_code == 200
    assert not [record for record in caplog.records if record.name == "pygeoapi.l10n"]


def test_sample_data_paths_do_not_expose_repository_files(http_client):
    assert http_client.get("/sample-data/../app.py").status_code == 404
    assert http_client.get("/sample-data/missing.tif").status_code == 404


def test_official_schema_snapshot_integrity():
    hashes = json.loads((ROOT / "SHA256SUMS.json").read_text())
    for name, expected in hashes.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
