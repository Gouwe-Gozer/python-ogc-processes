"""Exercise the contributor example through existing processor/manager interfaces."""

import importlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft4Validator
from pygeoapi.openapi import validate_openapi_document
from test_ogc_schemas import validate_official

from geo_processes.errors import InvalidExecutionRequestError
from geo_processes.manager import OgcSynchronousManager
from geo_processes.openapi import generate_openapi

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/custom-process"


@pytest.fixture()
def example_config(service_config, monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLE))
    config = deepcopy(service_config)
    config["resources"].update(yaml.safe_load((EXAMPLE / "process.yml").read_text()))
    return config


def manager(config):
    return OgcSynchronousManager(
        {"name": "geo_processes.manager.OgcSynchronousManager", "processes": config["resources"]}
    )


@pytest.mark.parametrize("response", ["raw", "document"])
@pytest.mark.parametrize("qualified", [False, True])
def test_example_function_runs_through_existing_manager(example_config, response, qualified):
    text = "Bring your own Python!"
    value = {"value": text, "mediaType": "application/json"} if qualified else text
    _, media_type, result, _, _ = manager(example_config).execute_process(
        "text-statistics", {"text": value}, requested_response=response
    )
    assert media_type == "application/json"
    expected = {"characters": 22, "words": 4}
    if response == "document":
        validate_official(result, "results.yaml")
        expected = {"statistics": {"value": expected}}
    assert result == expected


def test_example_description_and_openapi_match_execution(example_config):
    processor = manager(example_config).get_processor("text-statistics")
    validate_official(processor.metadata, "process.yaml")
    # Generation must not mutate the reusable metadata/schema constants.
    before = deepcopy(processor.metadata)
    document = generate_openapi(example_config)
    assert validate_openapi_document(document)
    assert manager(example_config).get_processor("text-statistics").metadata == before
    execution = document["paths"]["/processes/text-statistics/execution"]["post"]
    assert "raster" not in execution["responses"]["413"]["description"]
    payload = json.loads((EXAMPLE / "request.json").read_text())
    Draft4Validator(execution["requestBody"]["content"]["application/json"]["schema"]).validate(payload)
    _, _, result, _, _ = manager(example_config).execute_process(
        "text-statistics", payload["inputs"], requested_response=payload["response"]
    )
    Draft4Validator(execution["responses"]["200"]["content"]["application/json"]["schema"]).validate(result)


@pytest.mark.parametrize(
    "inputs,outputs",
    [
        ({}, None),
        ({"text": 1}, None),
        ({"text": "x" * 4097}, None),
        ({"text": "ok", "extra": True}, None),
        ({"text": "ok"}, {"unknown": {}}),
        ({"text": "ok"}, {"statistics": {"transmissionMode": "reference"}}),
        ({"text": "ok"}, {"statistics": {"format": {"mediaType": "text/plain"}}}),
        ({"text": {"href": "http://127.0.0.1/private", "type": "application/json"}}, None),
    ],
)
def test_example_reuses_controlled_input_and_output_errors(example_config, inputs, outputs):
    with pytest.raises(InvalidExecutionRequestError):
        manager(example_config).execute_process("text-statistics", inputs, requested_outputs=outputs)


def test_plain_function_can_be_called_directly(example_config):
    operation = importlib.import_module("custom_processes.operation")
    assert operation.text_statistics("") == {"characters": 0, "words": 0}
