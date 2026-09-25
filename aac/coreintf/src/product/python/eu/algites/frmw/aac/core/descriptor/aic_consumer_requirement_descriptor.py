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
class AIcConsumerRequirementDescriptor:
    id: str
    capability_id: str
    versions: tuple[int, ...]
    cardinality: AInConsumerCardinality = AInConsumerCardinality.SINGLE
    mandatory: bool = True
    requested_authorizations: tuple[str, ...] = ()
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.capability_id:
            raise ValueError("consumer requirement id/capability must not be empty")
        if any(version < 1 for version in self.versions):
            raise ValueError("consumer requirement versions must be >= 1")
        if len(self.versions) != len(set(self.versions)):
            raise ValueError("consumer requirement versions must be unique")
        if len(self.requested_authorizations) != len(set(self.requested_authorizations)):
            raise ValueError("requested authorization permissions must be unique")
