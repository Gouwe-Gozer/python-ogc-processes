"""An explicit HTTP representation for processors with non-default responses."""

from dataclasses import dataclass, field
from typing import Any

# Private manager-to-Flask metadata. Removed before sending any HTTP response.
STATUS_HEADER = "X-Terrio-Internal-Status"


@dataclass(frozen=True)
class ProcessResponse:
    body: Any
    media_type: str
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
