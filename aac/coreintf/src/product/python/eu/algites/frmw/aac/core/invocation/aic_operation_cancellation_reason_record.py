from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

from ..presentation.api import AIcDisplayText


def _require_instant(value: datetime, field: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware instant")


@dataclass(frozen=True, slots=True)
class AIcOperationCancellationReasonRecord:
    """Current active request for one framework-assigned cancellation reason."""

    reason: str
    current_deadline: datetime
    first_requested_at: datetime
    last_requested_at: datetime
    request_count: int = 1
    last_message: AIcDisplayText | None = None
    last_origin: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("cancellation reason must be non-empty")
        for field in ("current_deadline", "first_requested_at", "last_requested_at"):
            _require_instant(getattr(self, field), field)
        if self.last_requested_at < self.first_requested_at:
            raise ValueError("last_requested_at cannot precede first_requested_at")
        if self.request_count < 1:
            raise ValueError("request_count must be positive")
