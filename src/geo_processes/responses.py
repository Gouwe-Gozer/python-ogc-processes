"""An explicit HTTP representation for processors with non-default responses."""

from dataclasses import dataclass, field
from typing import Any

from jinja2.utils import htmlsafe_json_dumps
from pygeoapi.util import json_serial

# Private manager-to-Flask metadata. Removed before sending any HTTP response.
STATUS_HEADER = "X-Geo-Internal-Status"


@dataclass(frozen=True)
class ProcessResponse:
    body: Any
    media_type: str
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)


def htmlsafe_json(value, *, pretty=False):
    """Preserve JSON values while escaping HTML delimiters as Unicode sequences."""
    return str(htmlsafe_json_dumps(value, default=json_serial, indent=4 if pretty else None, separators=(",", ":")))
