"""Verify Rasterio metadata, bounds and real pixel semantics on local data."""

import ast
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from jsonschema import Draft202012Validator

from geo_processes import engine
from geo_processes.contracts.info import INFO_SCHEMA
from geo_processes.datasets import DEMO_RASTER


def test_raster_info_reports_exact_fixture_values():
    info = engine.raster_info(DEMO_RASTER)
    assert info["size"] == [4, 3]
    assert info["band_count"] == 1
    assert info["extent"] == [155000, 462970, 155040, 463000]
    assert info["crs"]["epsg"] == 28992
    assert info["bands"][0]["statistics"] == {
        "min": 1.0,
        "max": 12.0,
        "mean": 6.5,
        "std_dev": pytest.approx(3.4520525295),
        "valid_count": 12,
    }


def test_adapter_has_no_ogc_dependency():
    source = Path(engine.__file__).read_text()
    imports = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import | ast.ImportFrom)]
    assert all("pygeoapi" not in ast.unparse(node) for node in imports)


def test_missing_raster_has_a_sanitized_error(tmp_path):
    with pytest.raises(engine.RasterInfoError, match="configured raster could not be inspected") as error:
        engine.raster_info(tmp_path / "secret.tif")
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("data", [b"", b"not a raster", b"II\x2a\x00", b'{"type":"vector"}'])
def test_invalid_raster_content_is_rejected(tmp_path, data):
    source = tmp_path / "invalid.tif"
    source.write_bytes(data)
    with pytest.raises(engine.RasterInfoError):
        engine.raster_info(source)


def write_raster(tmp_path, values, *, nodata=None, crs="EPSG:28992"):
    source = tmp_path / "input.tif"
    data = np.asarray(values)
    if data.ndim == 2:
        data = data[np.newaxis, :, :]
    with rasterio.open(
        source,
        "w",
        driver="GTiff",
        width=data.shape[2],
        height=data.shape[1],
        count=data.shape[0],
        dtype=data.dtype,
        nodata=nodata,
        crs=crs,
        transform=rasterio.Affine(10, 0, 155000, 0, -10, 463000),
    ) as raster:
        raster.write(data)
        raster.update_tags(description="test raster")
    return source


@pytest.mark.parametrize(
    "nodata, expected", [(None, None), (-9999, -9999), (np.nan, "NaN"), (np.inf, "Infinity"), (-np.inf, "-Infinity")]
)
def test_nodata_and_nonfinite_samples_have_portable_json(tmp_path, nodata, expected):
    source = write_raster(tmp_path, np.array([[1, 2], [np.nan, np.inf]], dtype="float32"), nodata=nodata)
    info = engine.raster_info(source)
    Draft202012Validator(INFO_SCHEMA).validate(info)
    json.dumps(info, allow_nan=False)
    band = info["bands"][0]
    assert band["nodata"] == expected
    assert band["statistics"]["valid_count"] == 2
    assert band["statistics"]["mean"] == 1.5
    assert info["metadata"]["description"] == "test raster"


def test_empty_band_statistics_are_null(tmp_path):
    source = write_raster(tmp_path, np.full((2, 2), -9999, dtype="float32"), nodata=-9999)
    info = engine.raster_info(source)
    Draft202012Validator(INFO_SCHEMA).validate(info)
    assert info["bands"][0]["statistics"] == {"min": None, "max": None, "mean": None, "std_dev": None, "valid_count": 0}


def test_missing_crs_can_be_inspected_but_not_reprojected(tmp_path):
    source = write_raster(tmp_path, np.ones((2, 2), dtype="uint8"), crs=None)
    info = engine.raster_info(source)
    Draft202012Validator(INFO_SCHEMA).validate(info)
    assert info["crs"] is None and info["wgs84_extent"] is None
    with pytest.raises(engine.RasterWarpError):
        engine.warp_raster(source, tmp_path / "output.tif", "EPSG:4326", "nearest")
    assert not (tmp_path / "output.tif").exists()


def test_custom_crs_without_epsg_matches_contract(tmp_path):
    source = write_raster(
        tmp_path,
        np.ones((2, 2), dtype="float32"),
        crs="+proj=aeqd +lat_0=52.123 +lon_0=5.456 +datum=WGS84 +units=m +no_defs",
    )
    info = engine.raster_info(source)
    Draft202012Validator(INFO_SCHEMA).validate(info)
    assert info["crs"]["epsg"] is None
    assert info["crs"]["wkt"]


@pytest.mark.parametrize(
    "operation,error", [(engine.raster_info, engine.RasterInfoError), (engine.warp_raster, engine.RasterWarpError)]
)
def test_complex_rasters_fail_with_typed_errors(tmp_path, operation, error):
    source = write_raster(tmp_path, np.full((2, 2), 1 + 2j, dtype="complex64"))
    args = () if operation is engine.raster_info else (tmp_path / "output.tif", "EPSG:4326", "nearest")
    with pytest.raises(error):
        operation(source, *args)


def test_info_rejects_file_and_sample_bounds_before_reading_pixels(tmp_path, monkeypatch):
    source = write_raster(tmp_path, np.ones((2, 2), dtype="uint8"))
    monkeypatch.setattr(engine, "MAX_SAMPLES", 3)
    with pytest.raises(engine.RasterInfoError):
        engine.raster_info(source)
    monkeypatch.setattr(engine, "MAX_INPUT_BYTES", source.stat().st_size - 1)
    with pytest.raises(engine.RasterInfoError):
        engine.raster_info(source)


@pytest.mark.parametrize("method", ["nearest", "bilinear"])
def test_identity_warp_preserves_all_bands_nodata_and_transform(tmp_path, method):
    values = np.array([[[1, -9999], [3, 4]], [[10, 20], [-9999, 40]]], dtype="float32")
    source = write_raster(tmp_path, values, nodata=-9999)
    output = tmp_path / "output.tif"
    engine.warp_raster(source, output, "EPSG:28992", method)
    with rasterio.open(output) as raster:
        assert raster.crs.to_epsg() == 28992
        assert raster.count == 2
        assert raster.transform.to_gdal() == (155000, 10, 0, 463000, 0, -10)
        assert raster.nodata == -9999
        np.testing.assert_array_equal(raster.read(), values)
        assert raster.read(masked=True).count() == 6
