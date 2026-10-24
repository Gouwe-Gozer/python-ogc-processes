"""Integration of the three adapters with pygeoapi, OGC forms and delivery."""

import base64
import json
import os
import time
from copy import deepcopy
from urllib.parse import urlsplit

import numpy as np
import pytest
from jsonschema import Draft4Validator
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from test_ogc_schemas import validate_official

from geo_processes.contracts.polygonize import openapi_execution as polygon_contract
from geo_processes.contracts.reclassify import openapi_execution as reclassify_contract
from geo_processes.contracts.sample import GEOJSON_TYPE
from geo_processes.contracts.sample import openapi_execution as sample_contract
from geo_processes.openapi import generate_openapi
from geo_processes.storage import ResultStore, ResultStoreFullError

PROCESSES = ["raster-sample-points", "raster-reclassify", "raster-polygonize"]
CLASSES = [{"min": 0, "max": 2, "value": 10}, {"min": 2, "max": 4, "value": 20}]


def points(coordinates):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": index,
                "properties": {"label": str(index)},
                "geometry": {"type": "Point", "coordinates": coordinate},
            }
            for index, coordinate in enumerate(coordinates)
        ],
    }


def raster_source(values=None, *, crs="EPSG:4326", transform=None, nodata=255):
    values = np.array([[1, 1, 2], [1, 255, 2]], dtype="uint8") if values is None else values
    if values.ndim == 2:
        values = values[None, :, :]
    with MemoryFile() as memory:
        with memory.open(
            driver="GTiff",
            width=values.shape[2],
            height=values.shape[1],
            count=values.shape[0],
            dtype=values.dtype,
            crs=crs,
            transform=transform or from_origin(4, 54, 1, 1),
            nodata=nodata,
        ) as raster:
            raster.write(values)
        return {"value": base64.b64encode(memory.read()).decode(), "mediaType": "image/tiff", "encoding": "base64"}


@pytest.fixture(autouse=True)
def operation_directories(tmp_path, monkeypatch):
    monkeypatch.setenv("GEO_OUTPUT_DIR", str(tmp_path / "results"))
    monkeypatch.setenv("GEO_INPUT_TMPDIR", str(tmp_path / "inputs"))
    return tmp_path


def inputs_for(process):
    parameters = {"source": raster_source()}
    if process == "raster-sample-points":
        parameters["points"] = {"value": points([[4.5, 53.5], [5.5, 52.5], [20, 20]])}
    if process == "raster-reclassify":
        parameters["classes"] = deepcopy(CLASSES)
    return parameters


def execute(client, process, inputs, **options):
    return client.post(f"/processes/{process}/execution", json={"inputs": inputs, **options})


@pytest.mark.parametrize("process", PROCESSES)
def test_process_descriptions_and_binary_source_schema(http_client, process):
    response = http_client.get(f"/processes/{process}?f=json")
    assert response.status_code == 200
    description = response.get_json()
    validate_official(description, "process.yaml")
    assert description["jobControlOptions"] == ["sync-execute"]
    assert description["outputTransmission"] == ["value", "reference"]
    assert description["inputs"]["source"]["schema"]["contentMediaType"] == "image/tiff"
    assert "anyOf" not in description["inputs"]["source"]["schema"]
    if process == "raster-sample-points":
        assert description["inputs"]["points"]["schema"]["contentMediaType"] == GEOJSON_TYPE


@pytest.mark.parametrize("process", PROCESSES)
@pytest.mark.parametrize("response_mode", ["raw", "document"])
@pytest.mark.parametrize("transmission", ["value", "reference"])
def test_output_modes_metadata_and_downloads(http_client, process, response_mode, transmission):
    response = execute(
        http_client,
        process,
        inputs_for(process),
        response=response_mode,
        outputs={"result": {"transmissionMode": transmission}},
    )
    expected_type = "image/tiff" if process == "raster-reclassify" else GEOJSON_TYPE
    assert response.status_code == (204 if response_mode == "raw" and transmission == "reference" else 200)
    assert "Location" not in response.headers
    if transmission == "reference":
        if response_mode == "document":
            validate_official(response.get_json(), "results.yaml")
            url = response.get_json()["result"]["href"]
            assert response.get_json()["result"]["type"] == expected_type
        else:
            assert response.data == b""
            url = response.headers["Link"].split(">", 1)[0][1:]
            assert f'type="{expected_type}"' in response.headers["Link"]
        download = http_client.get(urlsplit(url).path)
        assert download.status_code == 200 and download.mimetype == expected_type
        assert "attachment" in download.headers["Content-Disposition"]
        assert download.headers["Expires"] and download.headers["X-Content-Type-Options"] == "nosniff"
        data = download.data
    elif response_mode == "document":
        result = response.get_json()["result"]
        assert result["mediaType"] == expected_type
        if expected_type == GEOJSON_TYPE:
            validate_official(response.get_json(), "results.yaml")
            data = json.dumps(result["value"]).encode()
        else:
            data = base64.b64decode(result["value"])
    else:
        assert response.mimetype == expected_type
        data = response.data
    if expected_type == "image/tiff":
        with MemoryFile(data) as memory, memory.open() as raster:
            assert raster.count == 1 and raster.dtypes == ("int32",)
            assert raster.crs.to_epsg() == 4326 and raster.transform == from_origin(4, 54, 1, 1)
            assert raster.nodata == -2147483648
            np.testing.assert_array_equal(raster.read(1), [[10, 10, 20], [10, -2147483648, 20]])
    else:
        document = json.loads(data)
        assert document["type"] == "FeatureCollection" and "crs" not in document
        features = document["features"]
        if process == "raster-sample-points":
            assert [item["properties"]["value"] for item in features] == [1, None, None]
            assert features[0]["id"] == 0 and features[0]["properties"]["label"] == "0"
        else:
            assert sorted(item["properties"]["value"] for item in features) == [1, 2]
            assert all(item["geometry"]["type"] == "Polygon" for item in features)


def test_sample_reprojects_points_and_selects_band(http_client):
    source = raster_source(
        np.array([[[1, 2]], [[7, 8]]], dtype="uint8"), crs="EPSG:3857", transform=from_origin(0, 100000, 100000, 100000)
    )
    response = execute(
        http_client,
        "raster-sample-points",
        {"source": source, "points": {"value": points([[0.5, 0.5], [1.5, 0.5]])}, "band": {"value": 2}},
    )
    assert response.status_code == 200
    assert [f["properties"]["value"] for f in json.loads(response.data)["features"]] == [7, 8]


def test_polygonize_reprojects_to_wgs84_and_excludes_masked_pixels(http_client):
    source = raster_source(crs="EPSG:3857", transform=from_origin(400000, 5400000, 1000, 1000))
    response = execute(http_client, "raster-polygonize", {"source": source, "connectivity": {"value": 4}})
    assert response.status_code == 200
    features = json.loads(response.data)["features"]
    assert len(features) == 2
    x, y = features[0]["geometry"]["coordinates"][0][0]
    assert 3 < x < 4 and 43 < y < 44
    for feature in features:
        ring = feature["geometry"]["coordinates"][0]
        assert sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:], strict=False)) > 0


def test_all_nodata_polygonization_returns_empty_collection(http_client):
    response = execute(http_client, "raster-polygonize", {"source": raster_source(np.full((2, 3), 255, dtype="uint8"))})
    assert response.status_code == 200
    assert json.loads(response.data) == {"type": "FeatureCollection", "features": []}


@pytest.mark.parametrize("connectivity,count", [(4, 4), (8, 2)])
def test_connectivity_is_passed_to_rasterio(http_client, connectivity, count):
    response = execute(
        http_client,
        "raster-polygonize",
        {"source": raster_source(np.array([[1, 2], [2, 1]], dtype="uint8")), "connectivity": connectivity},
    )
    assert response.status_code == 200
    assert len(json.loads(response.data)["features"]) == count


@pytest.mark.parametrize(
    "process,change",
    [
        ("raster-sample-points", {"points": points([[4, 53]])}),
        ("raster-sample-points", {"points": {"value": points([[200, 53]])}}),
        ("raster-sample-points", {"points": {"value": points([])}}),
        ("raster-reclassify", {"classes": [{"min": 0, "max": 2, "value": 1}, {"min": 1, "max": 3, "value": 2}]}),
        ("raster-reclassify", {"classes": [{"min": 1, "max": 1, "value": 2}]}),
        ("raster-reclassify", {"classes": [{"min": 0, "max": 1, "value": -2147483648}]}),
        ("raster-polygonize", {"connectivity": 6}),
        ("raster-polygonize", {"band": True}),
        ("raster-polygonize", {"band": 2}),
    ],
)
def test_invalid_parameters_are_ogc_errors(http_client, process, change):
    parameters = {**inputs_for(process), **change}
    response = execute(http_client, process, parameters)
    assert response.status_code == 400
    validate_official(response.get_json(), "exception.yaml")


@pytest.mark.parametrize("process", PROCESSES)
def test_unsupported_output_does_not_acquire_source(http_client, process, monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("unsupported outputs should be rejected before acquisition")

    monkeypatch.setattr("geo_processes.inputs._download", fail)
    response = execute(
        http_client,
        process,
        {**inputs_for(process), "source": {"href": "https://example.test/a.tif"}},
        outputs={"result": {"format": {"mediaType": "application/zip"}}},
    )
    assert response.status_code == 400


@pytest.mark.parametrize("process", ["raster-sample-points", "raster-polygonize"])
def test_georeferenced_operations_require_crs(http_client, process):
    response = execute(http_client, process, {**inputs_for(process), "source": raster_source(crs=None)})
    assert response.status_code == 400


def test_reclassify_preserves_missing_crs_and_handles_nonfinite_and_unmatched(http_client):
    response = execute(
        http_client,
        "raster-reclassify",
        {
            "source": raster_source(np.array([[0, 1, 2, 5, np.nan]], dtype="float32"), crs=None, nodata=None),
            "classes": {"value": [{"min": 0, "max": 2, "value": 9}]},
        },
    )
    assert response.status_code == 200
    with MemoryFile(response.data) as memory, memory.open() as raster:
        assert raster.crs is None
        np.testing.assert_array_equal(raster.read(1), [[9, 9, -2147483648, -2147483648, -2147483648]])


@pytest.mark.parametrize("kind", ["float", "pixels", "features", "bytes"])
def test_polygon_limits_clean_partial_outputs(http_client, operation_directories, monkeypatch, kind):
    source = raster_source()
    if kind == "float":
        source = raster_source(np.ones((2, 3), dtype="float32"), nodata=None)
    elif kind == "pixels":
        monkeypatch.setattr("geo_processes.operations.polygonize.MAX_POLYGON_PIXELS", 5)
    elif kind == "features":
        monkeypatch.setattr("geo_processes.operations.polygonize.MAX_FEATURES", 1)
    else:
        monkeypatch.setattr("geo_processes.operations.vector.MAX_VECTOR_BYTES", 20)
    response = execute(http_client, "raster-polygonize", {"source": source})
    assert response.status_code == 400
    assert not list((operation_directories / "results").glob("*.geojson"))
    assert not list((operation_directories / "results").glob(".work-*"))
    assert not list((operation_directories / "inputs").glob("slot-*"))


def test_geojson_shares_quota_and_expiry_with_tiff(http_client, operation_directories, monkeypatch):
    store = ResultStore.from_environment()
    old = store.publish(lambda path: path.write_bytes(b"tiff"))
    monkeypatch.setenv("GEO_RESULT_MAX_COUNT", "1")
    response = execute(http_client, "raster-polygonize", inputs_for("raster-polygonize"))
    assert response.status_code == 503
    old_path = store.root / f"{old.identifier}.tif"
    then = time.time() - 86401
    os.utime(old_path, (then, then))
    response = execute(
        http_client,
        "raster-polygonize",
        inputs_for("raster-polygonize"),
        response="document",
        outputs={"result": {"transmissionMode": "reference"}},
    )
    assert response.status_code == 200 and not old_path.exists()
    url = response.get_json()["result"]["href"]
    path = store.root / urlsplit(url).path.split("/")[-2]
    path = path.with_suffix(".geojson")
    os.utime(path, (then, then))
    assert http_client.get(urlsplit(url).path).status_code == 404
    assert http_client.get(urlsplit(url).path.replace("geojson", "tif")).status_code == 404
    assert http_client.get(urlsplit(url).path.replace("geojson", "zip")).status_code == 404


@pytest.mark.parametrize(
    "process,contract", list(zip(PROCESSES, [sample_contract, reclassify_contract, polygon_contract], strict=True))
)
def test_advertised_execution_contract_matches_requests_and_results(http_client, process, contract, monkeypatch):
    parameters = inputs_for(process)
    original_source = parameters["source"]

    def fetch(_url, destination, **_kwargs):
        destination.write_bytes(base64.b64decode(original_source["value"]))

    monkeypatch.setattr("geo_processes.inputs._fetch", fetch)
    parameters["source"] = {"href": "https://example.test/raster.tif"}
    payload = {"inputs": parameters, "response": "document", "outputs": {"result": {"transmissionMode": "reference"}}}
    validate_official(payload, "execute.yaml")
    operation = contract()
    Draft4Validator(operation["requestBody"]["content"]["application/json"]["schema"]).validate(payload)
    response = http_client.post(f"/processes/{process}/execution", json=payload)
    assert response.status_code == 200
    Draft4Validator(operation["responses"]["200"]["content"]["application/json"]["schema"]).validate(
        response.get_json()
    )


def test_geojson_publication_failure_is_sanitized(http_client, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("/private/secret")

    monkeypatch.setattr("geo_processes.operations.vector.write_features", fail)
    monkeypatch.setattr("geo_processes.operations.polygonize.write_features", fail)
    response = execute(http_client, "raster-polygonize", inputs_for("raster-polygonize"))
    assert response.status_code == 500
    assert "secret" not in response.text


def test_store_refuses_unknown_format_and_counts_geojson_bytes(tmp_path):
    store = ResultStore(tmp_path, max_bytes=5)
    with pytest.raises(ValueError):
        store.publish(lambda path: path.write_bytes(b"x"), extension="zip")
    store.publish(lambda path: path.write_bytes(b"1234"), extension="geojson")
    with pytest.raises(ResultStoreFullError):
        store.publish(lambda path: path.write_bytes(b"12"))


@pytest.mark.parametrize("process,extension", [("raster-polygonize", "geojson"), ("raster-reclassify", "tif")])
def test_download_routes_are_described_without_warp(service_config, process, extension):
    config = deepcopy(service_config)
    config["resources"] = {process: config["resources"][process]}
    paths = generate_openapi(config)["paths"]
    route = paths[f"/results/{{result_id}}/output.{extension}"]["get"]
    assert route["tags"] == [process] and "200" in route["responses"]
    assert "/processes/raster-warp" not in paths
