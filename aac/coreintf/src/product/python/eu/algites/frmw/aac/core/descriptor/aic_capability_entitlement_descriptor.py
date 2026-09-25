from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..capability.api import AIcProvidedCapability, AInConsumerCardinality
from ..instances.api import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness.api import AIcReadinessRequirementDescriptor

from .aic_permission_descriptor import AIcPermissionDescriptor

@dataclass(frozen=True, slots=True)
class AIcCapabilityEntitlementDescriptor:
    capability_id: str
    capability_version: int
    permissions: tuple[AIcPermissionDescriptor, ...]
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.capability_id or self.capability_version < 1:
            raise ValueError("capability entitlement requires capability id/version")
        permission_ids = [permission.id for permission in self.permissions]
        if len(permission_ids) != len(set(permission_ids)):
            raise ValueError("permission ids must be unique inside one capability-version entitlement declaration")

    def permission(self, permission_id: str) -> AIcPermissionDescriptor:
        for permission in self.permissions:
            if permission.id == permission_id:
                return permission
        raise KeyError(permission_id)
