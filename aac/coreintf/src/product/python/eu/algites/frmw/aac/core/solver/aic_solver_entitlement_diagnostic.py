from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from ..readiness.api import AInReadinessState

@dataclass(frozen=True, slots=True)
class AIcSolverEntitlementDiagnostic:
    component_id: str
    capability_id: str
    capability_version: int
    permission_id: str
    possible_licensing_scopes: tuple[str, ...] = ()
    granted: bool = False
    entitlement_info_url: str | None = None
