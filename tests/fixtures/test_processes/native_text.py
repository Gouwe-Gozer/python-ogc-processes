"""Test-only native string results through the ordinary processor interface."""

from pygeoapi.process.base import BaseProcessor


class NativeTextProcessor(BaseProcessor):
    def __init__(self, definition):
        super().__init__(
            definition,
            {
                "id": "native-text",
                "version": "1.0.0",
                "title": "Native text fixture",
                "jobControlOptions": ["sync-execute"],
                "outputTransmission": ["value"],
                "inputs": {
                    "media_type": {"schema": {"type": "string"}},
                    "value": {"schema": {"type": "string"}},
                },
                "outputs": {"result": {"schema": {"type": "string"}}},
            },
        )

    def execute(self, data, outputs=None):
        return data["media_type"], data["value"]
