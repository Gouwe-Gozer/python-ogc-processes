"""Opt-in experiments reusing the existing disposable API/DB/worker fixture."""

import base64
import os

import numpy as np
import pytest
import requests
from jsonschema import Draft4Validator
from rasterio.io import MemoryFile
from shapely.geometry import box, shape
from test_async_containers import deployment as container_deployment
from test_async_containers import poll, submit
from test_contributor_processes import PROCESS_IDS, assert_terrain_fixture, valid_inputs
from test_ogc_schemas import validate_official

deployment = container_deployment

pytestmark = pytest.mark.skipif(
    os.environ.get("GEO_TEST_ASYNC_CONTAINERS") != "1", reason="opt-in Docker lifecycle tests"
)


@pytest.mark.parametrize("deployment", ["contributor-experience"], indirect=True)
@pytest.mark.parametrize("process", PROCESS_IDS)
@pytest.mark.parametrize("response_mode", ["raw", "document"])
def test_contributor_discovery_openapi_sync_and_actual_worker(deployment, process, response_mode):
    base = deployment["url"]
    listing = requests.get(base + "/processes?f=json", timeout=5).json()
    assert process in {item["id"] for item in listing["processes"]}
    description = requests.get(base + f"/processes/{process}?f=json", timeout=5)
    assert description.status_code == 200
    validate_official(description.json(), "process.yaml")
    assert description.json()["jobControlOptions"] == ["sync-execute", "async-execute"]
    specification = requests.get(base + "/openapi?f=json", timeout=5).json()
    operation = specification["paths"][f"/processes/{process}/execution"]["post"]
    assert {"200", "201", "400", "503"} <= set(operation["responses"])
    html = requests.get(base + "/openapi?f=html", timeout=5)
    assert html.status_code == 200 and "swagger-ui" in html.text.lower()
    payload = {"inputs": valid_inputs(process), "response": response_mode}
    Draft4Validator(operation["requestBody"]["content"]["application/json"]["schema"]).validate(payload)
    synchronous = requests.post(base + f"/processes/{process}/execution", json=payload, timeout=15)
    assert synchronous.status_code == 200, synchronous.text
    job = submit(deployment, process, inputs=payload["inputs"], response=response_mode)
    assert poll(job)["status"] == "successful"
    asynchronous = requests.get(job + "/results", timeout=5)
    assert asynchronous.status_code == 200
    assert asynchronous.headers["Content-Type"] == synchronous.headers["Content-Type"]
    if process == "raster-convert-dtype" and response_mode == "raw":
        assert asynchronous.content == synchronous.content
    else:
        assert asynchronous.json() == synchronous.json()
    if process == "raster-convert-dtype":
        data = (
            asynchronous.content if response_mode == "raw" else base64.b64decode(asynchronous.json()["result"]["value"])
        )
        with MemoryFile(data) as memory, memory.open() as raster:
            assert raster.crs.to_epsg() == 28992
            assert raster.dtypes == ("int16",)
            np.testing.assert_array_equal(raster.read(1), [[1, 2], [-2, -9999]])
    elif process == "terrain-analysis":
        assert_terrain_fixture(
            asynchronous.json() if response_mode == "raw" else asynchronous.json()["terrain"]["value"]
        )
    else:
        value = asynchronous.json() if response_mode == "raw" else asynchronous.json()["intersection"]["value"]
        assert shape(value).equals(box(1, 1, 2, 2))
    if response_mode == "document":
        Draft4Validator(operation["responses"]["200"]["content"]["application/json"]["schema"]).validate(
            asynchronous.json()
        )
        if process != "raster-convert-dtype":
            validate_official(asynchronous.json(), "results.yaml")


@pytest.mark.parametrize("deployment", ["contributor-experience"], indirect=True)
@pytest.mark.parametrize("response_mode", ["raw", "document"])
@pytest.mark.parametrize("transmission", ["value", "reference"])
def test_conversion_all_delivery_modes_through_worker(deployment, response_mode, transmission):
    job = submit(
        deployment,
        "raster-convert-dtype",
        inputs=valid_inputs("raster-convert-dtype"),
        response=response_mode,
        outputs={"result": {"transmissionMode": transmission}},
    )
    assert poll(job)["status"] == "successful"
    synchronous = requests.post(
        deployment["url"] + "/processes/raster-convert-dtype/execution",
        json={
            "inputs": valid_inputs("raster-convert-dtype"),
            "response": response_mode,
            "outputs": {"result": {"transmissionMode": transmission}},
        },
        timeout=10,
    )
    for result in (synchronous, requests.get(job + "/results", timeout=5)):
        if transmission == "reference":
            if response_mode == "raw":
                assert result.status_code == 204 and not result.content
                href = result.headers["Link"].split("<", 1)[1].split(">", 1)[0]
            else:
                assert result.status_code == 200
                validate_official(result.json(), "results.yaml")
                href = result.json()["result"]["href"]
            download = requests.get(href, timeout=5)
            assert download.status_code == 200 and download.headers["Content-Type"] == "image/tiff"
            binary = download.content
        else:
            assert result.status_code == 200
            binary = result.content if response_mode == "raw" else base64.b64decode(result.json()["result"]["value"])
        with MemoryFile(binary) as memory, memory.open() as raster:
            np.testing.assert_array_equal(raster.read_masks(1), [[255, 255], [255, 0]])


@pytest.mark.parametrize("deployment", ["contributor-experience"], indirect=True)
@pytest.mark.parametrize("process", PROCESS_IDS)
def test_contributor_failed_jobs_preserve_typed_validation_errors(deployment, process):
    inputs = {**valid_inputs(process), "unrecognized": 1}
    synchronous = requests.post(
        deployment["url"] + f"/processes/{process}/execution", json={"inputs": inputs}, timeout=10
    )
    assert synchronous.status_code == 400
    job = submit(deployment, process, inputs=inputs)
    assert poll(job)["status"] == "failed"
    asynchronous = requests.get(job + "/results", timeout=5)
    assert asynchronous.status_code == 400
    assert asynchronous.json() == synchronous.json()
    validate_official(asynchronous.json(), "exception.yaml")


@pytest.mark.skipif(os.environ.get("GEO_TEST_LIVE_PDOK") != "1", reason="opt-in live PDOK test")
@pytest.mark.parametrize("deployment", ["contributor-live"], indirect=True)
def test_live_pdok_sync_and_actual_worker_without_mock(deployment):
    inputs = {"lat": 52.63, "lon": 4.75, "buffer_300m": 30, "buffer_500m": 50}
    synchronous = requests.post(
        deployment["url"] + "/processes/terrain-analysis/execution",
        json={"inputs": inputs, "response": "document"},
        timeout=290,
    )
    assert synchronous.status_code == 200, synchronous.text
    job = submit(deployment, "terrain-analysis", inputs=inputs, response="document")
    assert poll(job)["status"] == "successful"
    asynchronous = requests.get(job + "/results", timeout=5)
    assert asynchronous.status_code == 200
    for response in (synchronous, asynchronous):
        validate_official(response.json(), "results.yaml")
        terrain = response.json()["terrain"]["value"]
        assert terrain["is_partial"] is False, terrain["fetch_failures"]
        assert terrain["buffer_300m"]["pct_in_alkmaar"] == 100
        assert terrain["buffer_500m"]["oppervlak_bebouwd_pct"] > 0
