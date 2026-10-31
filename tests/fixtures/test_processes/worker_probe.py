"""Test-only slow operation for observable worker interruption and deadlines."""

import time

from pygeoapi.process.base import BaseProcessor


class WorkerProbe(BaseProcessor):
    def __init__(self, definition):
        super().__init__(
            definition,
            {
                "id": "worker-probe",
                "version": "1.0.0",
                "title": "Worker test probe",
                "description": "Test only",
                "jobControlOptions": ["sync-execute"],
                "outputTransmission": ["value"],
                "inputs": {"delay": {"title": "Delay", "schema": {"type": "number", "minimum": 0, "maximum": 20}}},
                "outputs": {"delay": {"title": "Delay", "schema": {"type": "number"}}},
            },
        )

    def execute(self, data, outputs=None):
        delay = max(0, min(20, float(data.get("delay", 0))))
        time.sleep(delay)
        return "application/json", {"delay": delay}
