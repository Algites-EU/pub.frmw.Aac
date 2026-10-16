from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

from .aic_operation_interaction_caller_to_provider_message import AIcOperationInteractionCallerToProviderMessage
from .aic_operation_cancellation_reason_record import _require_instant


@dataclass(frozen=True, slots=True)
class AIcOperationCancellationAcceptance:
    """Provider's local, irrevocable decision, reported when transport permits."""
    accepted_interaction_snapshot: AIcOperationInteractionCallerToProviderMessage
    accepted_reasons: frozenset[str]
    accepted_at: datetime

    def __post_init__(self) -> None:
        _require_instant(self.accepted_at, "accepted_at")
        if not self.accepted_reasons:
            raise ValueError("acceptance requires at least one reason")
        if any(not isinstance(reason, str) or not reason for reason in self.accepted_reasons):
            raise ValueError("accepted reasons must be non-empty identifiers")
        if not self.accepted_reasons.issubset(self.accepted_interaction_snapshot.cancellation_schedule):
            raise ValueError("accepted reasons must exist in the received interaction snapshot")
        for reason in self.accepted_reasons:
            deadline = self.accepted_interaction_snapshot.cancellation_schedule[reason].current_deadline
            if deadline > self.accepted_at:
                raise ValueError(f"reason {reason} is not effective at accepted_at")


def accept_cancellation_locally(
    snapshot: AIcOperationInteractionCallerToProviderMessage,
    reasons: frozenset[str] | set[str],
    *,
    at: datetime | None = None,
) -> AIcOperationCancellationAcceptance:
    """No round-trip or controller approval; uses the provider's last received snapshot."""
    return AIcOperationCancellationAcceptance(snapshot, frozenset(reasons), at or datetime.now(timezone.utc))


def effective_cancellation_reasons(
    snapshot: AIcOperationInteractionCallerToProviderMessage, *,
    at: datetime | None = None,
) -> frozenset[str]:
    """Effective reasons at the provider's local instant; no saved boolean state."""
    now = at or datetime.now(timezone.utc)
    _require_instant(now, "at")
    return frozenset(
        reason for reason, record in snapshot.cancellation_schedule.items()
        if record.current_deadline <= now
    )
