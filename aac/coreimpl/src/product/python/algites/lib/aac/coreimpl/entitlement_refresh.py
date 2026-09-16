from __future__ import annotations

from datetime import datetime, timezone

from algites.lib.aac.coreintf.entitlement import AIcEntitlementContext


def _parse(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


class AIcEntitlementRefreshPlanner:
    """Find the earliest effective-entitlement transition cached by Core."""

    @staticmethod
    def due(contexts: tuple[AIcEntitlementContext, ...], now: datetime | None = None) -> bool:
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        for context in contexts:
            transition = _parse(context.next_transition_at)
            if transition is not None and transition <= instant:
                return True
        return False
