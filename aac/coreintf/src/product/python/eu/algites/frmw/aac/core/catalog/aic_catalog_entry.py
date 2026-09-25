from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AInConsumerCardinality
from ..descriptor.api import AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor
from ..presentation.api import AIcDisplayText
from ..packages.api import AIcPackageSidecar

from .aic_catalog_component import AIcCatalogComponent
from .aic_catalog_release import AIcCatalogRelease

@dataclass(frozen=True, slots=True)
class AIcCatalogEntry:
    source_id: str
    product_id: str
    technology_id: str
    component: AIcCatalogComponent
    release: AIcCatalogRelease

    def __post_init__(self) -> None:
        if not self.source_id or not self.product_id or not self.technology_id:
            raise ValueError("catalog entry requires source/product/technology")

    @property
    def component_id(self) -> str:
        return self.component.component_id

    @property
    def component_version(self) -> int:
        return self.release.version
