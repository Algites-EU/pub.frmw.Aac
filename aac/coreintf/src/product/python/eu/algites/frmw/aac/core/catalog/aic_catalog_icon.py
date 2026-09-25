from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AInConsumerCardinality
from ..descriptor.api import AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor
from ..presentation.api import AIcDisplayText
from ..packages.api import AIcPackageSidecar

@dataclass(frozen=True, slots=True)
class AIcCatalogIcon:
    url: str

    def __post_init__(self) -> None:
        if not self.url:
            raise ValueError("catalog icon url must not be empty")
