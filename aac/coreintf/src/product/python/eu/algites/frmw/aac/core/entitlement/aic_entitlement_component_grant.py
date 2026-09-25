from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_entitlement_capability_grant import AIcEntitlementCapabilityGrant

@dataclass(frozen=True, slots=True)
class AIcEntitlementComponentGrant:
    component_id: str
    grants: tuple[AIcEntitlementCapabilityGrant, ...]

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("entitlement component grant component_id must not be empty")
        identities = [(item.capability_id, item.capability_version) for item in self.grants]
        if len(identities) != len(set(identities)):
            raise ValueError("capability id/version grants must be unique inside one entitlement component entry")
