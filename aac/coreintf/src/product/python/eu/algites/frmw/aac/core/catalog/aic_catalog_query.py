from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AInConsumerCardinality
from ..descriptor.api import AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor
from ..presentation.api import AIcDisplayText
from ..packages.api import AIcPackageSidecar

@dataclass(frozen=True, slots=True)
class AIcCatalogQuery:
    """Technology-scoped catalog query.

    ``product_id`` and ``technology_id`` are mandatory AAC catalog dimensions.
    Component ids and versions are interpreted only inside that scope.
    """

    product_id: str
    technology_id: str
    component_id: str | None = None
    versions: tuple[int, ...] = ()
    text: str | None = None
    provides_capability_id: str | None = None
    requires_capability_id: str | None = None
    categories: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.product_id or not self.technology_id:
            raise ValueError("catalog query requires product_id and technology_id")
        if any(version < 1 for version in self.versions):
            raise ValueError("catalog query versions must be >= 1")
