from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..capability.api import AIcProvidedCapability, AInConsumerCardinality
from ..instances.api import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness.api import AIcReadinessRequirementDescriptor

@dataclass(frozen=True, slots=True)
class AIcEntitlementLicensingScopeDescriptor:
    type: str
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = self.type.strip()
        if not normalized:
            raise ValueError("entitlement licensing scope type must not be empty")
        object.__setattr__(self, "type", normalized)
