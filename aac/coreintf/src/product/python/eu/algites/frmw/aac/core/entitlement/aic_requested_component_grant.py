from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_requested_capability_grant import AIcRequestedCapabilityGrant

@dataclass(frozen=True, slots=True)
class AIcRequestedComponentGrant:
    component_id: str
    requested_grants: tuple[AIcRequestedCapabilityGrant, ...]

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("requested component id must not be empty")
        identities = [(item.capability_id, item.capability_version) for item in self.requested_grants]
        if len(identities) != len(set(identities)):
            raise ValueError("requested capability id/version grants must be unique")
