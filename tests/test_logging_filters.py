"""Retain upstream metadata/localization while filtering false locale probes."""

import logging

import pytest
from pygeoapi import l10n
from test_ogc_schemas import validate_official

from geo_processes.logging_filters import MetadataLocaleFilter, install_metadata_locale_filter


@pytest.mark.parametrize(
    "path",
    [
        "/processes",
        "/processes/raster-info",
        "/processes/raster-warp",
        "/processes/raster-sample-points",
        "/processes/raster-reclassify",
        "/processes/raster-polygonize",
    ],
)
def test_process_discovery_does_not_log_schema_keys_as_locales(http_client, caplog, path):
    with caplog.at_level(logging.WARNING, logger="pygeoapi.l10n"):
        response = http_client.get(path + "?f=json")
    assert response.status_code == 200
    validate_official(response.get_json(), "processList.yaml" if path == "/processes" else "process.yaml")
    assert not [record for record in caplog.records if record.name == "pygeoapi.l10n"]


def test_filter_leaves_actual_descriptions_unchanged(http_client, monkeypatch, caplog):
    logger = logging.getLogger("pygeoapi.l10n")
    filtered = http_client.get("/processes/raster-sample-points?f=json").get_json()
    with monkeypatch.context() as context:
        context.setattr(logger, "filters", [])
        with caplog.at_level(logging.WARNING, logger="pygeoapi.l10n"):
            original = http_client.get("/processes/raster-sample-points?f=json").get_json()
    assert any("unknown locale" in record.getMessage() for record in caplog.records)
    assert filtered == original


def test_invalid_locales_and_other_warnings_are_still_visible(http_client, caplog):
    with caplog.at_level(logging.WARNING):
        with pytest.raises(l10n.LocaleError):
            l10n.str2locale("zz-ZZ")
        # A silent malformed tag is not the metadata-key diagnostic either.
        assert l10n.str2locale("invalid locale syntax", True) is None
        logging.getLogger("pygeoapi.l10n").warning("unrelated localization warning")
        logging.getLogger("geo_processes").warning("processing capacity warning")
    messages = [record.getMessage() for record in caplog.records]
    assert any("zz_ZZ" in message for message in messages)
    assert any("invalid locale syntax" in message for message in messages)
    assert "unrelated localization warning" in messages and "processing capacity warning" in messages


def test_filter_uses_registered_data_keys_and_keeps_translation_mistakes(monkeypatch, caplog):
    logger = logging.getLogger("pygeoapi.l10n")
    monkeypatch.setattr(logger, "filters", [])
    metadata = {
        "title": {"zz-ZZ": "Bad translation"},
        "inputs": {
            "points": {
                "schema": {
                    "type": "object",
                    "properties": {"customMeasurement": {"type": "number"}},
                }
            }
        },
        "example": {"inputs": {"customMeasurement": 4}},
    }
    install_metadata_locale_filter([metadata])
    install_metadata_locale_filter([metadata])
    assert len(logger.filters) == 1 and isinstance(logger.filters[0], MetadataLocaleFilter)
    with caplog.at_level(logging.WARNING, logger="pygeoapi.l10n"):
        assert l10n.str2locale("customMeasurement", True) is None
        assert l10n.str2locale("zz-ZZ", True) is None
        assert l10n.translate({"en": "Title", "nl": "Titel"}, "nl") == "Titel"
    assert len(caplog.records) == 1 and "zz_ZZ" in caplog.records[0].getMessage()
