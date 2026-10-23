"""Real GeoTIFF reprojection through the engine and every supported HTTP mode."""

import base64
import json
import os
import time
import urllib.request
from urllib.parse import urlsplit

import pytest
import rasterio
from jsonschema import Draft202012Validator

from geo_processes import engine
from geo_processes.contracts.warp import DOCUMENT_SCHEMA, EXECUTE_SCHEMA, RESAMPLING_METHODS, TARGET_CRSS
from geo_processes.datasets import DATASETS
from geo_processes.storage import ResultStore

EXECUTION = "/processes/raster-warp/execution"
INPUTS = {"source": "demo-dem", "target_crs": "EPSG:4326"}


def inspect_bytes(data, tmp_path):
    path = tmp_path / "download.tif"
    path.write_bytes(data)
    with rasterio.open(path) as raster:
        return {
            "driver": raster.driver,
            "crs": {"epsg": raster.crs.to_epsg()},
            "size": [raster.width, raster.height],
            "band_count": raster.count,
            "geo_transform": list(raster.transform.to_gdal()),
            "extent": list(raster.bounds),
            "bands": [{"statistics": {"valid_count": int(raster.read(1, masked=True).count())}}],
        }


def assert_raster(data, tmp_path, epsg=4326):
    info = inspect_bytes(data, tmp_path)
    assert info["driver"] == "GTiff"
    assert info["crs"]["epsg"] == epsg
    assert info["size"] == [4, 3]
    assert info["band_count"] == 1
    assert info["bands"][0]["statistics"]["valid_count"] > 0
    return info


@pytest.mark.parametrize("crs", TARGET_CRSS)
@pytest.mark.parametrize("method", RESAMPLING_METHODS)
def test_engine_warp_preserves_bounded_grid_and_reprojects(tmp_path, crs, method):
    output = tmp_path / "warped.tif"
    engine.warp_raster(DATASETS["demo-dem"], output, crs, method)
    info = assert_raster(output.read_bytes(), tmp_path, int(crs.split(":")[1]))
    if crs == "EPSG:28992":
        assert info["geo_transform"] == [155000, 10, 0, 463000, 0, -10]
    elif crs == "EPSG:4326":
        assert 5 < info["extent"][0] < 6
        assert 52 < info["extent"][1] < 53


def test_resampling_choice_changes_reprojected_samples(tmp_path):
    pixels = []
    for method in RESAMPLING_METHODS:
        output = tmp_path / f"{method}.tif"
        engine.warp_raster(DATASETS["demo-dem"], output, "EPSG:4326", method)
        with rasterio.open(output) as raster:
            pixels.append(raster.read(1))
    assert not (pixels[0] == pixels[1]).all()


def test_engine_limits_are_checked_before_warp(tmp_path, monkeypatch):
    source = tmp_path / "oversized.tif"
    with source.open("wb") as stream:
        stream.truncate(engine.MAX_INPUT_BYTES + 1)
    with pytest.raises(engine.RasterWarpError):
        engine.warp_raster(source, tmp_path / "output.tif", "EPSG:4326", "bilinear")

    class OversizedRaster:
        width = engine.MAX_SAMPLES + 1
        height = count = 1

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

    monkeypatch.setattr(engine.rasterio, "open", lambda *args, **kwargs: OversizedRaster())
    with pytest.raises(engine.RasterWarpError):
        engine.warp_raster(DATASETS["demo-dem"], tmp_path / "output.tif", "EPSG:4326", "bilinear")


@pytest.mark.parametrize("mode", ["raw", "document"])
@pytest.mark.parametrize("transmission", ["value", "reference"])
def test_all_response_and_transmission_combinations(http_client, tmp_path, mode, transmission):
    request = {"inputs": INPUTS, "response": mode, "outputs": {"result": {"transmissionMode": transmission}}}
    Draft202012Validator(EXECUTE_SCHEMA).validate(request)
    response = http_client.post(EXECUTION, json=request)
    assert "X-Geo-Internal-Status" not in response.headers
    assert "Location" not in response.headers
    if mode == "raw" and transmission == "reference":
        assert response.status_code == 204
        assert not response.data
        assert 'type="image/tiff"' in response.headers["Link"]
        href = response.headers["Link"].split("<", 1)[1].split(">", 1)[0]
    else:
        assert response.status_code == 200
        if mode == "raw":
            assert response.content_type == "image/tiff"
            assert_raster(response.data, tmp_path)
            return
        assert response.mimetype == "application/json"
        document = response.get_json()
        Draft202012Validator(DOCUMENT_SCHEMA).validate(document)
        if transmission == "value":
            assert document["result"]["encoding"] == "base64"
            assert_raster(base64.b64decode(document["result"]["value"], validate=True), tmp_path)
            return
        href = document["result"]["href"]
    assert urlsplit(href).scheme == "http"
    download = http_client.get(urlsplit(href).path)
    assert download.status_code == 200
    assert download.content_type == "image/tiff"
    assert download.headers["Cache-Control"] == "no-store"
    assert download.headers["Expires"]
    assert_raster(download.data, tmp_path)


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"outputs": {"result": {}}},
        {"outputs": {"result": {"format": {}}}},
        {"outputs": {"result": {"format": {"mediaType": "image/tiff"}}}},
    ],
)
def test_omitted_response_outputs_and_transmission_default_to_native_tiff(http_client, tmp_path, options):
    response = http_client.post(EXECUTION, json={"inputs": INPUTS, **options})
    assert response.status_code == 200
    assert response.content_type == "image/tiff"
    assert_raster(response.data, tmp_path)


@pytest.mark.parametrize("accept", ["image/tiff", "*/*"])
def test_native_output_accept_header(http_client, accept):
    response = http_client.post(EXECUTION, json={"inputs": INPUTS}, headers={"Accept": accept})
    assert response.status_code == 200
    assert response.mimetype == "image/tiff"


def test_async_preference_is_still_synchronous(http_client):
    response = http_client.post(EXECUTION, json={"inputs": INPUTS}, headers={"Prefer": "respond-async"})
    assert response.status_code == 200
    assert "Preference-Applied" not in response.headers
    assert "Location" not in response.headers
    assert response.mimetype == "image/tiff"


@pytest.mark.parametrize(
    "document",
    [
        {"inputs": {}},
        {"inputs": {"source": "demo-dem"}},
        {"inputs": {**INPUTS, "target_crs": "EPSG:9999"}},
        {"inputs": {**INPUTS, "target_crs": True}},
        {"inputs": {**INPUTS, "resampling": "cubic"}},
        {"inputs": {**INPUTS, "resampling": []}},
        {"inputs": {**INPUTS, "resolution": 1}},
        {"inputs": {**INPUTS, "source": "../../secret.tif"}},
        {"inputs": {**INPUTS, "source": "https://example.test/raster.tif"}},
        {"inputs": {**INPUTS, "source": {"href": "https://example.test/raster.tif"}}},
        {"inputs": INPUTS, "outputs": {}},
        {"inputs": INPUTS, "outputs": {"unknown": {}}},
        {"inputs": INPUTS, "outputs": {"result": []}},
        {"inputs": INPUTS, "outputs": {"result": {"transmissionMode": []}}},
        {"inputs": INPUTS, "outputs": {"result": {"transmissionMode": "unsupported"}}},
        {"inputs": INPUTS, "outputs": {"result": {"format": None}}},
        {"inputs": INPUTS, "outputs": {"result": {"format": {"mediaType": "application/json"}}}},
        {"inputs": INPUTS, "outputs": {"result": {"format": {"encoding": "gzip"}}}},
        {"inputs": INPUTS, "outputs": {"result": {"unknown": True}}},
        {"inputs": INPUTS, "subscriber": {"successUri": "https://example.test/callback"}},
    ],
)
def test_invalid_warp_requests_never_start_rasterio(http_client, monkeypatch, document):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid input must not reach Rasterio")

    monkeypatch.setattr(engine, "warp_raster", forbidden)
    assert not Draft202012Validator(EXECUTE_SCHEMA).is_valid(document)
    response = http_client.post(EXECUTION, json=document)
    assert response.status_code == 400
    assert response.is_json
    assert response.get_json()["type"] == "InvalidParameterValue"
    assert "Traceback" not in response.text


def test_capacity_and_busy_storage_are_controlled_503s(http_client, tmp_path, monkeypatch):
    monkeypatch.setenv("GEO_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("GEO_RESULT_MAX_COUNT", "1")
    assert http_client.post(EXECUTION, json={"inputs": INPUTS}).status_code == 200
    response = http_client.post(EXECUTION, json={"inputs": INPUTS})
    assert response.status_code == 503
    assert response.is_json
    with ResultStore.from_environment()._writer():
        response = http_client.post(EXECUTION, json={"inputs": INPUTS})
    assert response.status_code == 503
    assert "another raster operation" in response.get_json()["description"]


def test_engine_failure_is_sanitized_and_cleans_workspace(http_client, tmp_path, monkeypatch):
    monkeypatch.setenv("GEO_OUTPUT_DIR", str(tmp_path))

    def fail(*args, **kwargs):
        raise RuntimeError("/secret/internal/raster.tif")

    monkeypatch.setattr(engine, "reproject", fail)
    response = http_client.post(EXECUTION, json={"inputs": INPUTS})
    assert response.status_code == 500
    assert "secret" not in response.text
    assert not list(tmp_path.glob(".work-*"))
    assert not list(tmp_path.glob("*.tif"))


def test_download_rejects_expired_missing_or_invalid_ids(http_client, tmp_path, monkeypatch):
    monkeypatch.setenv("GEO_OUTPUT_DIR", str(tmp_path))
    document = {"inputs": INPUTS, "response": "document", "outputs": {"result": {"transmissionMode": "reference"}}}
    response = http_client.post(EXECUTION, json=document)
    href = response.get_json()["result"]["href"]
    path = urlsplit(href).path
    assert http_client.get(path).status_code == 200
    stored = next(tmp_path.glob("*.tif"))
    then = time.time() - 86401
    os.utime(stored, (then, then))
    expired = http_client.get(path)
    assert expired.status_code == 404
    assert expired.get_json()["type"] == "NoSuchResult"
    assert http_client.get("/results/invalid/output.tif").status_code == 404
    assert http_client.get(f"/results/{'a' * 32}/output.tif").status_code == 404


def test_description_and_openapi_match_actual_modes(http_client):
    description = http_client.get("/processes/raster-warp?f=json").get_json()
    assert description["jobControlOptions"] == ["sync-execute"]
    assert description["outputTransmission"] == ["value", "reference"]
    assert description["outputs"]["result"]["schema"]["contentMediaType"] == "image/tiff"
    paths = http_client.get("/openapi?f=json").get_json()["paths"]
    operation = paths[EXECUTION]["post"]
    assert "201" not in operation["responses"]
    assert "204" in operation["responses"]
    assert "503" in operation["responses"]
    assert set(operation["responses"]["200"]["content"]) == {"image/tiff", "application/json"}
    assert "/results/{result_id}/output.tif" in paths


@pytest.mark.parametrize("mode", ["raw", "document"])
def test_reference_result_is_downloadable_over_real_http(http_server, tmp_path, mode):
    payload = {"inputs": INPUTS, "response": mode, "outputs": {"result": {"transmissionMode": "reference"}}}
    request = urllib.request.Request(
        f"{http_server}{EXECUTION}", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if mode == "raw":
            assert response.status == 204
            assert response.read() == b""
            href = response.headers["Link"].split("<", 1)[1].split(">", 1)[0]
        else:
            assert response.status == 200
            href = json.load(response)["result"]["href"]
    assert href.startswith(http_server + "/results/")
    with urllib.request.urlopen(href, timeout=10) as download:
        assert download.status == 200
        assert download.headers.get_content_type() == "image/tiff"
        assert_raster(download.read(), tmp_path)


def test_oversized_execute_document_is_a_json_413(http_client):
    response = http_client.post(EXECUTION, json={"inputs": {**INPUTS, "source": "x" * (16 * 1024)}})
    assert response.status_code == 413
    assert response.is_json
    assert response.get_json()["type"] == "RequestTooLarge"


def test_warp_openapi_schemas_validate_actual_documents(http_client):
    operation = http_client.get("/openapi?f=json").get_json()["paths"][EXECUTION]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    document_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    for transmission in ("value", "reference"):
        payload = {"inputs": INPUTS, "response": "document", "outputs": {"result": {"transmissionMode": transmission}}}
        Draft202012Validator(request_schema).validate(payload)
        response = http_client.post(EXECUTION, json=payload)
        assert response.status_code == 200
        Draft202012Validator(document_schema).validate(response.get_json())


def test_reference_url_uses_configuration_not_request_host(http_client):
    from pygeoapi.flask_app import api_

    payload = {"inputs": INPUTS, "response": "document", "outputs": {"result": {"transmissionMode": "reference"}}}
    response = http_client.post(EXECUTION, json=payload, headers={"Host": "untrusted.example"})
    assert response.status_code == 200
    href = response.get_json()["result"]["href"]
    assert href.startswith(api_.manager.result_base_url + "/results/")
    assert "untrusted.example" not in href


def test_invalid_public_url_prevents_reference_processing(http_client, monkeypatch):
    from pygeoapi.flask_app import api_

    monkeypatch.setattr(api_.manager, "result_base_url", "file:///private/results")

    def forbidden(*args, **kwargs):
        pytest.fail("invalid public URL must be rejected before processing")

    monkeypatch.setattr(engine, "warp_raster", forbidden)
    payload = {"inputs": INPUTS, "response": "document", "outputs": {"result": {"transmissionMode": "reference"}}}
    response = http_client.post(EXECUTION, json=payload)
    assert response.status_code == 500
    assert "private" not in response.text


def test_result_read_failure_is_sanitized(http_client, monkeypatch):
    from geo_processes.storage import ResultStoreError

    def fail(*args, **kwargs):
        raise ResultStoreError("/secret/storage/path")

    monkeypatch.setattr(ResultStore, "read", fail)
    response = http_client.get(f"/results/{'a' * 32}/output.tif")
    assert response.status_code == 500
    assert response.is_json
    assert "secret" not in response.text
    assert response.get_json()["description"] == "result could not be read"
