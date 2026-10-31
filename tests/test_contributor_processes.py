"""Independent integration experiments using the documented extension workflow."""

import base64
import json
import os
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
import rasterio
import requests
import yaml
from jsonschema import Draft4Validator
from pygeoapi.openapi import validate_openapi_document
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from shapely.geometry import Point, box, mapping, shape
from terrain_pdok import fake_pdok_get
from test_ogc_schemas import validate_official

from geo_processes.errors import InvalidExecutionRequestError
from geo_processes.manager import OgcSynchronousManager
from geo_processes.openapi import generate_openapi
from geo_processes.operations.convert_dtype import convert_dtype
from geo_processes.operations.intersection import geometry_intersection

REGISTRATIONS = Path("examples/contributor-experience/processes.yml")
PROCESS_IDS = ("geometry-intersection", "raster-convert-dtype", "terrain-analysis")


def qualified(geometry):
    return {"value": json.loads(json.dumps(mapping(geometry))), "mediaType": "application/geo+json"}


def conversion_source(values=None, *, dtype="float64", nodata=-9999):
    values = np.array([[[1.5, 2.5], [-2.8, -9999]]], dtype=dtype) if values is None else np.asarray(values, dtype=dtype)
    with MemoryFile() as memory:
        with memory.open(
            driver="GTiff",
            width=values.shape[2],
            height=values.shape[1],
            count=values.shape[0],
            dtype=dtype,
            crs="EPSG:28992",
            transform=from_origin(100000, 500000, 2, 2),
            nodata=nodata,
        ) as raster:
            raster.write(values)
            raster.update_tags(project="contributor experiment")
            raster.update_tags(1, sensor="fixture", STATISTICS_MINIMUM="-9999")
            raster.set_band_description(1, "Elevation")
            raster.set_band_unit(1, "m")
            raster.scales = tuple(0.5 for _ in raster.indexes)
            raster.offsets = tuple(10 for _ in raster.indexes)
        return {"value": base64.b64encode(memory.read()).decode(), "mediaType": "image/tiff", "encoding": "base64"}


def valid_inputs(process):
    return {
        "geometry-intersection": {"left": qualified(box(0, 0, 2, 2)), "right": qualified(box(1, 1, 3, 3))},
        "raster-convert-dtype": {"source": conversion_source(), "dtype": "int16"},
        "terrain-analysis": {"lat": 52.63, "lon": 4.75},
    }[process]


@pytest.fixture()
def contributor_config(service_config, tmp_path, monkeypatch):
    monkeypatch.setenv("GEO_OUTPUT_DIR", str(tmp_path / "results"))
    monkeypatch.setenv("GEO_INPUT_TMPDIR", str(tmp_path / "inputs"))
    config = deepcopy(service_config)
    config["resources"].update(yaml.safe_load(REGISTRATIONS.read_text()))
    return config


def manager(config):
    instance = OgcSynchronousManager(
        {"name": "geo_processes.manager.OgcSynchronousManager", "processes": config["resources"]}
    )
    instance.result_base_url = "http://example.test"
    return instance


def test_intersection_function_covers_geometry_types_and_empty_results():
    result = geometry_intersection(qualified(box(0, 0, 2, 2))["value"], qualified(box(1, 1, 3, 3))["value"])
    assert shape(result).equals(box(1, 1, 2, 2))


@pytest.mark.parametrize(
    "left,right,expected",
    [
        (Point(0, 0), box(-1, -1, 1, 1), Point(0, 0)),
        (box(0, 0, 1, 1), box(1, 0, 2, 1), box(0, 0, 1, 1).boundary.intersection(box(1, 0, 2, 1).boundary)),
    ],
)
def test_intersection_preserves_lower_dimensional_results(left, right, expected):
    assert shape(geometry_intersection(qualified(left)["value"], qualified(right)["value"])).equals(expected)


def test_disjoint_intersection_is_finite_empty_geojson():
    result = geometry_intersection(qualified(Point(0, 0))["value"], qualified(Point(1, 1))["value"])
    assert result == {"type": "GeometryCollection", "geometries": []}
    assert geometry_intersection(result, result) == result


@pytest.mark.parametrize(
    "bad",
    [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 0]}},
        {"type": "Point", "coordinates": [181, 0]},
        {"type": "Point", "coordinates": [10**400, 0]},
        {"type": "Point", "coordinates": [0, 0, 1]},
        {"type": "Point", "coordinates": [True, 0]},
        {"type": "Point", "coordinates": [float("nan"), 0]},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]},
        {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
    ],
)
def test_intersection_rejects_invalid_geometry(bad):
    with pytest.raises(ValueError):
        geometry_intersection(bad, {"type": "Point", "coordinates": [0, 0]})


@pytest.mark.parametrize("dtype", ["uint8", "uint16", "int16", "float32", "float64"])
def test_convert_all_target_types_and_relevant_metadata(tmp_path, dtype):
    source = tmp_path / "source.tif"
    output = tmp_path / "output.tif"
    source.write_bytes(base64.b64decode(conversion_source([[[1, 2], [3, -9999]], [[4, 5], [-9999, 6]]])["value"]))
    convert_dtype(source, output, dtype, nodata=255)
    with rasterio.open(source) as before, rasterio.open(output) as after:
        assert after.dtypes == (dtype, dtype)
        assert (after.crs, after.transform, after.count, after.width, after.height) == (
            before.crs,
            before.transform,
            2,
            2,
            2,
        )
        assert after.descriptions == before.descriptions and after.units == before.units
        assert after.scales == before.scales and after.offsets == before.offsets
        assert after.tags()["project"] == "contributor experiment"
        assert after.tags(1) == {"sensor": "fixture"}
        assert after.nodata == 255
        np.testing.assert_array_equal(after.read_masks(), before.read_masks())
        np.testing.assert_array_equal(after.read(1), [[1, 2], [3, 255]])
        np.testing.assert_array_equal(after.read(2), [[4, 5], [255, 6]])
        assert output.with_suffix(".tif.msk").exists() is False


@pytest.mark.parametrize("rounding,expected", [("truncate", [[1, 2], [-2, -9999]]), ("nearest", [[2, 2], [-3, -9999]])])
def test_float_to_integer_rounding_is_explicit(tmp_path, rounding, expected):
    source, output = tmp_path / "source.tif", tmp_path / "output.tif"
    source.write_bytes(base64.b64decode(conversion_source()["value"]))
    convert_dtype(source, output, "int16", rounding=rounding)
    with rasterio.open(output) as raster:
        np.testing.assert_array_equal(raster.read(1), expected)


def test_conversion_rejects_wraparound_and_clips_only_explicitly(tmp_path):
    source, output = tmp_path / "source.tif", tmp_path / "output.tif"
    source.write_bytes(base64.b64decode(conversion_source([[[-1, 256], [10, -9999]]])["value"]))
    with pytest.raises(ValueError, match="overflow"):
        convert_dtype(source, output, "uint8", nodata=254)
    convert_dtype(source, output, "uint8", nodata=254, overflow="clip")
    with rasterio.open(output) as raster:
        np.testing.assert_array_equal(raster.read(1), [[0, 255], [10, 254]])


@pytest.mark.parametrize(
    "pixels,options,match",
    [
        ([[[1, 2], [3, -9999]]], {}, "nodata is not representable"),
        ([[[1, 2], [255, -9999]]], {"nodata": 255}, "collides"),
        ([[[1, 2], [3, -9999]]], {"nodata": 2.5}, "not representable"),
        ([[[float("inf"), 2], [3, -9999]]], {"nodata": 255}, "nonfinite valid"),
    ],
)
def test_conversion_rejects_ambiguous_nodata_and_nonfinite_values(tmp_path, pixels, options, match):
    source = tmp_path / "source.tif"
    source.write_bytes(base64.b64decode(conversion_source(pixels)["value"]))
    with pytest.raises(ValueError, match=match):
        convert_dtype(source, tmp_path / "output.tif", "uint8", **options)


def test_float32_overflow_and_nan_nodata(tmp_path):
    source, output = tmp_path / "source.tif", tmp_path / "output.tif"
    source.write_bytes(base64.b64decode(conversion_source([[[1e39, float("nan")]]], nodata=float("nan"))["value"]))
    with pytest.raises(ValueError, match="overflow"):
        convert_dtype(source, output, "float32")
    convert_dtype(source, output, "float32", overflow="clip")
    with rasterio.open(output) as raster:
        assert np.isnan(raster.nodata)
        assert raster.read(1)[0, 0] == np.finfo("float32").max
        assert raster.read_masks(1).tolist() == [[255, 0]]


def test_internal_mask_requires_a_destination_sentinel(tmp_path):
    source, output = tmp_path / "source.tif", tmp_path / "output.tif"
    source.write_bytes(base64.b64decode(conversion_source([[[0, 1], [2, 3]]], nodata=None)["value"]))
    with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True), rasterio.open(source, "r+") as raster:
        raster.write_mask(np.array([[0, 255], [255, 255]], dtype="uint8"))
    with pytest.raises(ValueError, match="explicit destination nodata"):
        convert_dtype(source, output, "uint8")
    convert_dtype(source, output, "uint8", nodata=255)
    with rasterio.open(output) as raster:
        np.testing.assert_array_equal(raster.read_masks(1), [[0, 255], [255, 255]])


def test_unmasked_nonfinite_pixels_and_nodata_free_integer_boundaries(tmp_path):
    source, output = tmp_path / "source.tif", tmp_path / "output.tif"
    source.write_bytes(base64.b64decode(conversion_source([[[0, 255]]], dtype="uint8", nodata=None)["value"]))
    convert_dtype(source, output, "uint8")
    with rasterio.open(output) as raster:
        assert raster.nodata is None
        np.testing.assert_array_equal(raster.read(1), [[0, 255]])
    source.write_bytes(base64.b64decode(conversion_source([[[float("nan"), 1]]], nodata=None)["value"]))
    with pytest.raises(ValueError, match="nonfinite valid"):
        convert_dtype(source, output, "float64")


@pytest.fixture()
def pdok(monkeypatch):
    from geo_processes.operations import terrain

    monkeypatch.setattr(terrain.requests, "get", fake_pdok_get)
    return terrain


def assert_terrain_fixture(result):
    assert result["is_partial"] is False and result["fetch_failures"] == {}
    for radius in (300, 500):
        percentages = result[f"buffer_{radius}m"]
        area = Point(0, 0).buffer(radius).area
        assert percentages["pct_in_alkmaar"] == 100
        # Independent rectangular areas; priority masking removes buildings,
        # roads and taller vegetation from the 40000 m2 grass square.
        for key, square_metres in {
            "lage_vegetatie": 25000,
            "middelhoge_vegetatie": 2500,
            "hoge_vegetatie": 2500,
            "water": 1600,
            "wegen": 5000,
            "bebouwd": 5000,
            "onverhard": 28200,
            "onbebouwd": 1600,
        }.items():
            assert percentages[f"oppervlak_{key}_pct"] == round(square_metres / area * 100, 2)


def test_original_terrain_category_mapping_priority_and_output(pdok):
    assert_terrain_fixture(pdok.get_terrain_analysis(52.63, 4.75))


def test_terrain_http_failure_preserves_original_partial_output(pdok, monkeypatch):
    def fail_water(url, **kwargs):
        if "/waterdeel/" in url:
            raise requests.Timeout("deterministic timeout")
        return fake_pdok_get(url, **kwargs)

    monkeypatch.setattr(pdok.requests, "get", fail_water)
    result = pdok.get_terrain_analysis(52.63, 4.75)
    assert result["is_partial"] is True
    assert result["fetch_failures"] == {"water": "http_error: deterministic timeout"}
    assert result["buffer_300m"]["oppervlak_water_pct"] == 0


def test_terrain_requests_json_errors_keep_original_http_error_classification(pdok, monkeypatch):
    def malformed(url, **kwargs):
        response = fake_pdok_get(url, **kwargs)
        response._content = b"not JSON"
        return response

    monkeypatch.setattr(pdok.requests, "get", malformed)
    result = pdok.get_terrain_analysis(52.63, 4.75)
    assert result["is_partial"] is True
    assert len(result["fetch_failures"]) == 5
    # Requests' JSONDecodeError is also a RequestException: the supplied
    # function's first except clause classifies it as http_error.
    assert all(value.startswith("http_error:") for value in result["fetch_failures"].values())


def test_terrain_tile_subdivision_deduplicates_ids(pdok, monkeypatch):
    calls = []

    def tiled(url, **kwargs):
        response = fake_pdok_get(url, **kwargs)
        if "/begroeidterreindeel/" in url:
            calls.append(kwargs["params"]["bbox"])
            if len(calls) == 1:
                features = response.json()["features"]
                response._content = json.dumps({"features": [features[0]] * 100}).encode()
        return response

    monkeypatch.setattr(pdok.requests, "get", tiled)
    assert_terrain_fixture(pdok.get_terrain_analysis(52.63, 4.75, limit=100))
    assert len(calls) == 5  # first full tile, then four smaller tiles


def test_original_global_geometry_dedup_can_discard_a_building(pdok, monkeypatch):
    def duplicated_across_categories(url, **kwargs):
        response = fake_pdok_get(url, **kwargs)
        vegetation = fake_pdok_get(
            "https://api.pdok.nl/lv/bgt/ogc/v1/collections/begroeidterreindeel/items", **kwargs
        ).json()["features"][0]
        features = [vegetation] if "/begroeidterreindeel/" in url or "/pand/" in url else []
        response._content = json.dumps({"features": features}).encode()
        return response

    monkeypatch.setattr(pdok.requests, "get", duplicated_across_categories)
    result = pdok.get_terrain_analysis(52.63, 4.75)
    assert result["is_partial"] is False
    assert result["buffer_300m"]["oppervlak_bebouwd_pct"] == 0
    assert result["buffer_300m"]["oppervlak_lage_vegetatie_pct"] > 0


def test_original_skipped_invalid_features_do_not_mark_output_partial(pdok, monkeypatch):
    def invalid_feature(url, **kwargs):
        response = fake_pdok_get(url, **kwargs)
        response._content = json.dumps({"features": [{"id": "broken", "properties": {}}]}).encode()
        return response

    monkeypatch.setattr(pdok.requests, "get", invalid_feature)
    result = pdok.get_terrain_analysis(52.63, 4.75)
    assert result["is_partial"] is False and result["fetch_failures"] == {}
    assert result["buffer_300m"]["oppervlak_lage_vegetatie_pct"] == 0


def test_terrain_missing_auxiliary_dataset_is_a_processing_failure(pdok, monkeypatch, tmp_path):
    pdok.load_alkmaar_polygon_rd.cache_clear()
    monkeypatch.setattr(pdok, "ALKMAAR_POLYGON_FILE", tmp_path / "missing.geojson")
    try:
        with pytest.raises(FileNotFoundError):
            pdok.get_terrain_analysis(52.63, 4.75)
    finally:
        pdok.load_alkmaar_polygon_rd.cache_clear()


@pytest.mark.parametrize("process", PROCESS_IDS)
def test_description_openapi_and_manager_execution(contributor_config, pdok, process):
    runtime = manager(contributor_config)
    metadata = deepcopy(runtime.get_processor(process).metadata)
    validate_official(metadata, "process.yaml")
    specification = generate_openapi(contributor_config)
    assert validate_openapi_document(specification)
    assert runtime.get_processor(process).metadata == metadata
    execution = specification["paths"][f"/processes/{process}/execution"]["post"]
    payload = {"inputs": valid_inputs(process), "response": "document"}
    Draft4Validator(execution["requestBody"]["content"]["application/json"]["schema"]).validate(payload)
    _, media, result, _, _ = runtime.execute_process(process, payload["inputs"], requested_response="document")
    assert media == "application/json"
    Draft4Validator(execution["responses"]["200"]["content"][media]["schema"]).validate(result)
    if process != "raster-convert-dtype":
        validate_official(payload, "execute.yaml")
        validate_official(result, "results.yaml")


@pytest.mark.parametrize("process", PROCESS_IDS)
@pytest.mark.parametrize("response_mode", ["raw", "document"])
def test_processes_through_real_http_adapter(
    contributor_config, pdok, process, response_mode, http_client, monkeypatch
):
    from pygeoapi.flask_app import api_

    monkeypatch.setattr(
        api_.manager,
        "processes",
        {key: value for key, value in contributor_config["resources"].items() if value["type"] == "process"},
    )
    listing = http_client.get("/processes?f=json").get_json()
    assert process in {item["id"] for item in listing["processes"]}
    description = http_client.get(f"/processes/{process}?f=json")
    validate_official(description.get_json(), "process.yaml")
    result = http_client.post(
        f"/processes/{process}/execution", json={"inputs": valid_inputs(process), "response": response_mode}
    )
    assert result.status_code == 200
    if process == "raster-convert-dtype":
        binary = result.data if response_mode == "raw" else base64.b64decode(result.get_json()["result"]["value"])
        with MemoryFile(binary) as memory, memory.open() as raster:
            assert raster.dtypes == ("int16",)
            np.testing.assert_array_equal(raster.read(1), [[1, 2], [-2, -9999]])
    elif process == "terrain-analysis":
        assert_terrain_fixture(result.get_json() if response_mode == "raw" else result.get_json()["terrain"]["value"])
    else:
        geometry = result.get_json() if response_mode == "raw" else result.get_json()["intersection"]["value"]
        assert shape(geometry).equals(box(1, 1, 2, 2))


@pytest.mark.parametrize(
    "process,inputs",
    [
        ("geometry-intersection", {"left": {"type": "Point", "coordinates": [0, 0]}, "right": qualified(Point(0, 0))}),
        ("geometry-intersection", {"left": {"href": "http://127.0.0.1/private"}, "right": qualified(Point(0, 0))}),
        ("raster-convert-dtype", {"source": conversion_source(), "dtype": "int8"}),
        ("raster-convert-dtype", {"source": conversion_source(), "dtype": "int16", "rounding": "magic"}),
        ("terrain-analysis", {"lat": True, "lon": 4.75}),
        ("terrain-analysis", {"lat": 10**400, "lon": 4.75}),
        ("terrain-analysis", {"lat": 52.63, "lon": 4.75, "buffer_300m": 0}),
        ("terrain-analysis", {"lat": 52.63, "lon": 4.75, "buffer_300m": 400, "buffer_500m": 300}),
        ("terrain-analysis", {"lat": 52.63, "lon": 4.75, "limit": 1}),
    ],
)
def test_invalid_inputs_use_existing_typed_errors(contributor_config, process, inputs):
    with pytest.raises(InvalidExecutionRequestError):
        manager(contributor_config).execute_process(process, inputs)


@pytest.mark.parametrize("process", PROCESS_IDS)
def test_output_selection_and_missing_inputs_are_validated(contributor_config, process):
    runtime = manager(contributor_config)
    for inputs, outputs in [
        ({}, None),
        ({**valid_inputs(process), "unknown": 1}, None),
        (valid_inputs(process), {"unknown": {}}),
    ]:
        with pytest.raises(InvalidExecutionRequestError):
            runtime.execute_process(process, inputs, requested_outputs=outputs)
    output = next(iter(runtime.get_processor(process).metadata["outputs"]))
    with pytest.raises(InvalidExecutionRequestError):
        runtime.execute_process(
            process, valid_inputs(process), requested_outputs={output: {"format": {"mediaType": "text/plain"}}}
        )
    if process != "raster-convert-dtype":
        with pytest.raises(InvalidExecutionRequestError):
            runtime.execute_process(
                process, valid_inputs(process), requested_outputs={output: {"transmissionMode": "reference"}}
            )


@pytest.mark.skipif(os.environ.get("GEO_TEST_LIVE_PDOK") != "1", reason="opt-in live PDOK test")
def test_live_pdok_terrain_function_and_source_schema():
    from geo_processes.contracts.terrain import RESULT_SCHEMA
    from geo_processes.operations.terrain import get_terrain_analysis

    result = get_terrain_analysis(52.63, 4.75, buffer_300m=30, buffer_500m=50)
    Draft4Validator(RESULT_SCHEMA).validate(result)
    assert result["is_partial"] is False, result["fetch_failures"]
    assert result["buffer_300m"]["pct_in_alkmaar"] == 100
    # A wholly empty response must not be mistaken for successful integration.
    assert result["buffer_500m"]["oppervlak_bebouwd_pct"] > 0
