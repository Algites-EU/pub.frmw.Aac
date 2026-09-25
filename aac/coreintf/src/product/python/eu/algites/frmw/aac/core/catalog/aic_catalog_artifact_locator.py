from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AInConsumerCardinality
from ..descriptor.api import AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor
from ..presentation.api import AIcDisplayText
from ..packages.api import AIcPackageSidecar

@dataclass(frozen=True, slots=True)
class AIcCatalogArtifactLocator:
    type: str
    uri: str | None = None
    repository_id: str | None = None
    coordinates: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.type:
            raise ValueError("catalog artifact locator type must not be empty")
        if self.type.upper() == "URI" and not self.uri:
            raise ValueError("URI catalog artifact locator requires uri")
        if self.type.upper() == "REPOSITORY" and not self.repository_id:
            raise ValueError("REPOSITORY catalog artifact locator requires repository_id")
