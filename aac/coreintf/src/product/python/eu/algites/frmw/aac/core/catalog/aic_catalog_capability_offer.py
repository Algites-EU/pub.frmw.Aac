from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AInConsumerCardinality
from ..descriptor.api import AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor
from ..presentation.api import AIcDisplayText
from ..packages.api import AIcPackageSidecar

@dataclass(frozen=True, slots=True)
class AIcCatalogCapabilityOffer:
    capability_id: str
    versions: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.capability_id or not self.versions or any(version < 1 for version in self.versions):
            raise ValueError("catalog capability offer requires id and versions >= 1")
        if len(self.versions) != len(set(self.versions)):
            raise ValueError("catalog capability offer versions must be unique")
