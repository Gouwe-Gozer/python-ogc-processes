"""Unit checks for the operation-specific OGC boundary."""

import pytest
from jsonschema import Draft202012Validator

from terrio_processes.contracts.info import DOCUMENT_SCHEMA, EXECUTE_SCHEMA, INFO_SCHEMA, PROCESS_METADATA
from terrio_processes.manager import InvalidExecutionRequestError
from terrio_processes.processes.info import TerrioInfoProcessor

DEFINITION = {"name": "terrio_processes.processes.info.TerrioInfoProcessor"}


@pytest.mark.parametrize("schema", [INFO_SCHEMA, EXECUTE_SCHEMA, DOCUMENT_SCHEMA])
def test_published_schema_is_valid(schema):
    Draft202012Validator.check_schema(schema)


def test_metadata_is_independent_of_upstream_mutation():
    processor = TerrioInfoProcessor(DEFINITION)
    processor.metadata["outputs"]["info"]["schema"].pop("contentMediaType")
    assert PROCESS_METADATA["outputs"]["info"]["schema"]["contentMediaType"] == "application/json"
    assert TerrioInfoProcessor(DEFINITION).supports_outputs


def test_processor_calls_real_terrio():
    processor = TerrioInfoProcessor(DEFINITION)
    media_type, output = processor.execute({"source": "demo-dem"})
    assert media_type == "application/json"
    Draft202012Validator(INFO_SCHEMA).validate(output)
    assert output["bands"][0]["statistics"]["valid_count"] == 12
    assert processor.format_result(output, "raw") == output
    assert processor.format_result(output, "document") == {"info": {"value": output}}


@pytest.mark.parametrize("inputs", [None, [], {}, {"source": False}, {"source": "demo-dem", "extra": 1}])
def test_invalid_inputs_fail_when_called_directly(inputs):
    with pytest.raises(InvalidExecutionRequestError):
        TerrioInfoProcessor(DEFINITION).execute(inputs)
