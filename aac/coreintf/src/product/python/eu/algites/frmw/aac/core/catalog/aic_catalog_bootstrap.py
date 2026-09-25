from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AInConsumerCardinality
from ..descriptor.api import AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor
from ..presentation.api import AIcDisplayText
from ..packages.api import AIcPackageSidecar

from .aic_catalog_source_registration import AIcCatalogSourceRegistration

@dataclass(frozen=True, slots=True)
class AIcCatalogBootstrap:
    schema_version: int
    product_id: str
    technology_id: str
    sources: tuple[AIcCatalogSourceRegistration, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version < 1 or not self.product_id or not self.technology_id:
            raise ValueError("catalog bootstrap requires schema_version/product_id/technology_id")
        ids = [source.id for source in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("catalog source ids must be unique")
