"""Small synchronous pygeoapi manager without output-type assumptions."""

import logging
from uuid import uuid4

from pygeoapi.api import processes as processes_api
from pygeoapi.process.base import ProcessorExecuteError
from pygeoapi.process.manager.dummy import DummyManager
from pygeoapi.util import JobStatus, RequestedProcessExecutionMode

from terrio_processes.responses import STATUS_HEADER, ProcessResponse

LOGGER = logging.getLogger(__name__)
CALLBACK_CONFORMANCE_URI = "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/callback"


class InvalidExecutionRequestError(ProcessorExecuteError):
    """An unsupported or malformed execution request."""

    http_status_code = 400
    ogc_exception_code = "InvalidParameterValue"

    def __init__(self, message):
        super().__init__(user_msg=message)


class OgcSynchronousManager(DummyManager):
    """Execute inline; let each operation own its result representation.

    DummyManager in pygeoapi 0.24.0 wraps document results in an outputs array
    and turns all exceptions into 400s. Keep upstream discovery/registration,
    preserve typed processor errors, and delegate output encoding to the process.
    """

    def __init__(self, manager_def):
        super().__init__(manager_def)
        # The Flask application supplies its canonical configured URL at startup.
        self.result_base_url = ""
        if CALLBACK_CONFORMANCE_URI in processes_api.CONFORMANCE_CLASSES:
            processes_api.CONFORMANCE_CLASSES.remove(CALLBACK_CONFORMANCE_URI)

    def execute_process(
        self,
        process_id,
        data_dict,
        execution_mode=None,
        requested_outputs=None,
        subscriber=None,
        requested_response="raw",
    ):
        if not isinstance(requested_response, str) or requested_response not in {"raw", "document"}:
            raise InvalidExecutionRequestError("response must be either raw or document")
        if subscriber is not None:
            raise InvalidExecutionRequestError("subscriber callbacks are not supported")

        processor = self.get_processor(process_id)
        processor.result_base_url = self.result_base_url
        headers = {}
        try:
            media_type, value = processor.execute(data_dict, outputs=requested_outputs)
            formatter = getattr(processor, "format_result", None)
            if formatter is not None:
                value = formatter(value, requested_response)
            elif requested_response == "document":
                raise InvalidExecutionRequestError("this process does not support document responses")
            if isinstance(value, ProcessResponse):
                media_type = value.media_type
                headers.update(value.headers)
                headers["Content-Type"] = media_type
                if value.status != 200:
                    headers[STATUS_HEADER] = str(value.status)
                value = value.body
        except ProcessorExecuteError:
            raise
        except Exception as error:
            LOGGER.exception("Unexpected process execution failure")
            raise ProcessorExecuteError(user_msg="process execution failed") from error

        if execution_mode == RequestedProcessExecutionMode.wait:
            headers["Preference-Applied"] = "wait"
        return str(uuid4()), media_type, value, JobStatus.successful, headers
