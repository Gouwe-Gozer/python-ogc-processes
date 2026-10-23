"""Verify the direct Rust-backed binding on deterministic local data."""

import ast
from pathlib import Path

import pytest

from terrio_processes import engine
from terrio_processes.contracts.info import DATASETS


def test_raster_info_reports_exact_fixture_values():
    info = engine.raster_info(DATASETS["demo-dem"])
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


@pytest.mark.parametrize("result", [None, [], {"type": "vector"}, {"type": "raster", "value": float("nan")}])
def test_invalid_engine_results_are_rejected(monkeypatch, result):
    monkeypatch.setattr(engine.terrio, "info", lambda *args, **kwargs: result)
    with pytest.raises(engine.RasterInfoError):
        engine.raster_info(DATASETS["demo-dem"])
