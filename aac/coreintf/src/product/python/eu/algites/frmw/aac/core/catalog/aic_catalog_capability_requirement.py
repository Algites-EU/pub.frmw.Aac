from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AInConsumerCardinality
from ..descriptor.api import AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor
from ..presentation.api import AIcDisplayText
from ..packages.api import AIcPackageSidecar

@dataclass(frozen=True, slots=True)
class AIcCatalogCapabilityRequirement:
    id: str
    capability_id: str
    versions: tuple[int, ...]
    cardinality: AInConsumerCardinality = AInConsumerCardinality.SINGLE
    mandatory: bool = True

    def __post_init__(self) -> None:
        if not self.id or not self.capability_id:
            raise ValueError("catalog capability requirement requires id/capability")
        if any(version < 1 for version in self.versions):
            raise ValueError("catalog capability requirement versions must be >= 1")
        if len(self.versions) != len(set(self.versions)):
            raise ValueError("catalog capability requirement versions must be unique")
