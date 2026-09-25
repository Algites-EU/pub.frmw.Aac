from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AInConsumerCardinality
from ..descriptor.api import AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor
from ..presentation.api import AIcDisplayText
from ..packages.api import AIcPackageSidecar

from .aic_catalog_component import AIcCatalogComponent

@dataclass(frozen=True, slots=True)
class AIcCatalogDocument:
    format_version: int
    product_id: str
    technology_id: str
    components: tuple[AIcCatalogComponent, ...]
    generated_at: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.format_version < 1 or not self.product_id or not self.technology_id:
            raise ValueError("catalog document requires format_version/product_id/technology_id")
        ids = [component.component_id for component in self.components]
        if len(ids) != len(set(ids)):
            raise ValueError("catalog components must be unique by component_id")
