"""Predictable, integration-only process for OGC conformance testing.

The process lets CITE test synchronous and asynchronous OGC API execution
without domain-specific inputs or live data. It is never
registered in the public service.
"""

import time

from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError

MAX_PAUSE_SECONDS = 60

PROCESS_METADATA = {
    "version": "0.2.0",
    "id": "async-echo",
    "title": "Asynchronous execution test fixture",
    "description": (
        "Integration-test process that returns a supplied string after an optional pause. "
        "It supports OGC CITE execution tests and is not part of the public API."
    ),
    "keywords": ["diagnostic", "async", "job manager"],
    "jobControlOptions": ["sync-execute", "async-execute"],
    "outputTransmission": ["value"],
    "inputs": {
        "message": {
            "title": "Message",
            "description": "Plain string returned unchanged by the process.",
            "schema": {"type": "string"},
            "minOccurs": 1,
            "maxOccurs": 1,
        },
        "pause": {
            "title": "Pause",
            "description": "Seconds to wait before returning the message.",
            "schema": {
                "type": "integer",
                "minimum": 0,
                "maximum": MAX_PAUSE_SECONDS,
                "default": 0,
            },
            "minOccurs": 0,
            "maxOccurs": 1,
        },
    },
    "outputs": {
        "message": {
            "title": "Message",
            "description": "The supplied message returned unchanged.",
            "schema": {"type": "string"},
        },
    },
    "example": {"inputs": {"message": "teststring", "pause": 0}},
}


class AsyncEchoProcessor(BaseProcessor):
    """Echo a plain string, with an optional pause for async job tests."""

    def __init__(self, processor_def):
        super().__init__(processor_def, PROCESS_METADATA)
        self.supports_outputs = True

    def execute(self, data, outputs=None):
        message = data.get("message")
        if not isinstance(message, str):
            raise ProcessorExecuteError("message must be a string")

        pause = data.get("pause", 0)
        if isinstance(pause, bool) or not isinstance(pause, int):
            raise ProcessorExecuteError("pause must be an integer")
        if not 0 <= pause <= MAX_PAUSE_SECONDS:
            raise ProcessorExecuteError(f"pause must be between 0 and {MAX_PAUSE_SECONDS}")

        time.sleep(pause)

        produced_output = {}
        if not outputs or "message" in outputs:
            produced_output = {"id": "message", "value": message}

        return "application/json", produced_output

    def __repr__(self):
        return f"<AsyncEchoProcessor> {self.name}"
