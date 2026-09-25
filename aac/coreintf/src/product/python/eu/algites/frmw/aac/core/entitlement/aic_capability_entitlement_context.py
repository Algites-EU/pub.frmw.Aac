from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_effective_entitlement_permission import AIcEffectiveEntitlementPermission

@dataclass(frozen=True, slots=True)
class AIcCapabilityEntitlementContext:
    capability_id: str
    capability_version: int
    permissions: Mapping[str, AIcEffectiveEntitlementPermission] = field(default_factory=dict)

    def has_permission(self, permission_id: str) -> bool:
        return permission_id in self.permissions
