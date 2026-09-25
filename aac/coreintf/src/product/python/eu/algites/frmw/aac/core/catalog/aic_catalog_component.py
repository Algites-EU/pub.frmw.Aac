from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AInConsumerCardinality
from ..descriptor.api import AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor
from ..presentation.api import AIcDisplayText
from ..packages.api import AIcPackageSidecar

from .aic_catalog_icon import AIcCatalogIcon
from .aic_catalog_publisher import AIcCatalogPublisher
from .aic_catalog_release import AIcCatalogRelease

@dataclass(frozen=True, slots=True)
class AIcCatalogComponent:
    component_id: str
    releases: tuple[AIcCatalogRelease, ...]
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    publisher: AIcCatalogPublisher | None = None
    homepage_url: str | None = None
    documentation_url: str | None = None
    support_url: str | None = None
    entitlement_info_url: str | None = None
    icon: AIcCatalogIcon | None = None
    categories: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("catalog component_id must not be empty")
        versions = [release.version for release in self.releases]
        if len(versions) != len(set(versions)):
            raise ValueError("catalog releases must be unique by version")
