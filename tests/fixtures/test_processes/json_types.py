"""Test-only results using types supported by pygeoapi's JSON encoder."""

from datetime import UTC, date, datetime, time
from decimal import Decimal

import numpy as np
from pygeoapi.process.base import BaseProcessor


class JsonTypesProcessor(BaseProcessor):
    def __init__(self, definition):
        super().__init__(
            definition,
            {
                "id": "json-types",
                "version": "1.0.0",
                "title": "JSON serialization fixture",
                "jobControlOptions": ["sync-execute"],
                "outputTransmission": ["value"],
                "inputs": {},
                "outputs": {"result": {"schema": {"type": "object"}}},
            },
        )

    def execute(self, data, outputs=None):
        return "application/json", {
            "timestamp": datetime(2026, 10, 31, 12, 34, 56, 123456, tzinfo=UTC),
            "date": date(2026, 10, 31),
            "time": time(12, 34, 56),
            "amount": Decimal("1.25"),
            "counts": [np.int32(7), np.int64(9007199254740993)],
            "nested": {"value": np.float32(1.25), "label": "Café </script><script> ' & <river>"},
        }

    @staticmethod
    def format_result(value, response):
        return {"result": {"value": value}} if response == "document" else value
