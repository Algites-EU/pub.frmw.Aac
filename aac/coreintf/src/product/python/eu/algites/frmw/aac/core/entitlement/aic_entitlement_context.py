from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_capability_entitlement_context import AIcCapabilityEntitlementContext

@dataclass(frozen=True, slots=True)
class AIcEntitlementContext:
    component_id: str
    capabilities: tuple[AIcCapabilityEntitlementContext, ...] = ()
    next_transition_at: str | None = None
    diagnostics: tuple[str, ...] = ()

    def capability(self, capability_id: str, capability_version: int) -> AIcCapabilityEntitlementContext | None:
        for item in self.capabilities:
            if item.capability_id == capability_id and item.capability_version == capability_version:
                return item
        return None

    def has_permission(self, capability_id: str, capability_version: int, permission_id: str) -> bool:
        capability = self.capability(capability_id, capability_version)
        return capability is not None and capability.has_permission(permission_id)
