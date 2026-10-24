"""Exercise the user-facing local-file command against the real HTTP service."""

import io
from email.message import Message

import pytest
import rasterio

from geo_processes.datasets import DEMO_RASTER
from scripts import process_raster


def test_local_file_command_inspects_reprojects_downloads_and_saves(http_server, tmp_path, monkeypatch, capsys):
    output = tmp_path / "my-output.tif"
    monkeypatch.setattr(
        "sys.argv",
        [
            "process_raster",
            str(DEMO_RASTER),
            "--base-url",
            http_server,
            "--output",
            str(output),
            "--target-crs",
            "EPSG:4326",
            "--resampling",
            "nearest",
        ],
    )
    assert process_raster.main() == 0
    with rasterio.open(output) as raster:
        assert raster.crs.to_epsg() == 4326
        assert raster.shape == (3, 4) and raster.count == 1
        assert raster.read(1).max() == 12
    text = capsys.readouterr().out
    assert "Source: 4 x 3, 1 band(s)" in text
    assert f"Saved EPSG:4326 GeoTIFF to {output}" in text
    assert list(tmp_path.iterdir()) == [output]


def test_existing_output_is_preserved_without_contacting_service(tmp_path):
    output = tmp_path / "existing.tif"
    output.write_bytes(b"keep me")
    with pytest.raises(process_raster.ClientError, match="already exists"):
        process_raster.process_raster("http://unreachable.invalid", DEMO_RASTER, output)
    assert output.read_bytes() == b"keep me"


def test_service_error_is_readable_and_does_not_create_output(http_server, tmp_path, monkeypatch, capsys):
    source = tmp_path / "bad.tif"
    source.write_bytes(b"not a TIFF")
    output = tmp_path / "output.tif"
    monkeypatch.setattr("sys.argv", ["process_raster", str(source), "--base-url", http_server, "--output", str(output)])
    assert process_raster.main() == 1
    assert "API returned HTTP 400:" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("content,maximum,length", [(b"too large", 4, None), (b"truncated", 100, "20")])
def test_failed_download_never_publishes_a_partial_file(tmp_path, monkeypatch, content, maximum, length):
    def execute(_base, process, _payload):
        if process == "raster-info":
            return {"size": [4, 3], "band_count": 1}
        return {"result": {"href": "https://example.test/results/output.tif", "type": "image/tiff"}}

    response = io.BytesIO(content)
    response.status = 200
    response.headers = Message()
    response.headers["Content-Type"] = "image/tiff"
    if length:
        response.headers["Content-Length"] = length
    monkeypatch.setattr(process_raster, "_execute", execute)
    monkeypatch.setattr(process_raster, "_open", lambda *_: response)
    monkeypatch.setattr(process_raster, "MAX_RESULT_BYTES", maximum)
    with pytest.raises(process_raster.ClientError, match="exceeds|incomplete"):
        process_raster.process_raster("https://example.test", DEMO_RASTER, tmp_path / "output.tif")
    assert list(tmp_path.iterdir()) == []
