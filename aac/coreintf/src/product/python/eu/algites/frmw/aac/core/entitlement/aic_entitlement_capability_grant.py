from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_entitlement_permission_grant import AIcEntitlementPermissionGrant

@dataclass(frozen=True, slots=True)
class AIcEntitlementCapabilityGrant:
    capability_id: str
    capability_version: int
    permissions: tuple[AIcEntitlementPermissionGrant, ...]

    def __post_init__(self) -> None:
        if not self.capability_id:
            raise ValueError("entitlement capability grant capability_id must not be empty")
        if self.capability_version < 1:
            raise ValueError("entitlement capability grant capability_version must be >= 1")
        ids = [item.id for item in self.permissions]
        if len(ids) != len(set(ids)):
            raise ValueError("permission ids must be unique inside one capability-version grant")
