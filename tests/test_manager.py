"""Keep manager behavior independent of JSON, output IDs and result counts."""

import pytest
from pygeoapi.process.base import ProcessorExecuteError
from pygeoapi.util import RequestedProcessExecutionMode

from geo_processes.errors import InputBusyError, InputTooLargeError, InvalidExecutionRequestError
from geo_processes.manager import OgcSynchronousManager


@pytest.fixture()
def manager():
    return OgcSynchronousManager({"name": "geo_processes.manager.OgcSynchronousManager"})


@pytest.mark.parametrize("response", [None, [], "unsupported"])
def test_manager_rejects_invalid_response(manager, response):
    with pytest.raises(InvalidExecutionRequestError):
        manager.execute_process("test", {}, requested_response=response)


def test_manager_rejects_callbacks(manager):
    with pytest.raises(InvalidExecutionRequestError, match="callbacks"):
        manager.execute_process("test", {}, subscriber=object())


@pytest.mark.parametrize(
    "error,status,code",
    [
        (InvalidExecutionRequestError("invalid input"), 400, "InvalidParameterValue"),
        (InputTooLargeError(user_msg="input too large"), 413, "RequestTooLarge"),
        (InputBusyError(user_msg="input capacity busy"), 503, "ServerBusy"),
    ],
)
def test_shared_execution_errors_keep_their_identity_and_http_contract(manager, monkeypatch, error, status, code):
    class Processor:
        def execute(self, *_args, **_kwargs):
            raise error

    monkeypatch.setattr(manager, "get_processor", lambda _: Processor())
    with pytest.raises(ProcessorExecuteError) as caught:
        manager.execute_process("test", {})
    assert caught.value is error
    assert caught.value.http_status_code == status
    assert caught.value.ogc_exception_code == code


def test_manager_preserves_native_bytes_and_media_type(manager, monkeypatch):
    class NativeProcessor:
        def execute(self, data, outputs=None):
            return "image/tiff", b"TIFF bytes"

    monkeypatch.setattr(manager, "get_processor", lambda _: NativeProcessor())
    _, media_type, result, _, headers = manager.execute_process(
        "native", {}, execution_mode=RequestedProcessExecutionMode.respond_async
    )
    assert media_type == "image/tiff"
    assert result == b"TIFF bytes"
    assert not headers
    with pytest.raises(InvalidExecutionRequestError, match="document"):
        manager.execute_process("native", {}, requested_response="document")


def test_manager_delegates_multi_output_formatting(manager, monkeypatch):
    class Processor:
        def execute(self, data, outputs=None):
            return "application/json", {"a": 1, "b": 2}

        def format_result(self, value, response):
            return value

    monkeypatch.setattr(manager, "get_processor", lambda _: Processor())
    assert manager.execute_process("example", {}, requested_response="document")[2] == {"a": 1, "b": 2}


def test_unexpected_processor_failure_is_sanitized(manager, monkeypatch):
    class BrokenProcessor:
        def execute(self, *args, **kwargs):
            raise RuntimeError("/private/path")

    monkeypatch.setattr(manager, "get_processor", lambda _: BrokenProcessor())
    with pytest.raises(ProcessorExecuteError) as error:
        manager.execute_process("broken", {})
    assert error.value.http_status_code == 500
    assert error.value.message == "process execution failed"
