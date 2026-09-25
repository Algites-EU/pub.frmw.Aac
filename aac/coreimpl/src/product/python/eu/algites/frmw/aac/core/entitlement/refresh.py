from __future__ import annotations
from datetime import datetime, timezone
from eu.algites.frmw.aac.core.entitlement.api import AIcEntitlementContext

from .aic_entitlement_refresh_planner import AIcEntitlementRefreshPlanner

def _parse(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
