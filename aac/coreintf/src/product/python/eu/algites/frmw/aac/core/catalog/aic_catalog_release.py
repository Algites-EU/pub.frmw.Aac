from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AInConsumerCardinality
from ..descriptor.api import AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor
from ..presentation.api import AIcDisplayText
from ..packages.api import AIcPackageSidecar

from .aic_catalog_artifact import AIcCatalogArtifact
from .aic_catalog_capability_offer import AIcCatalogCapabilityOffer
from .aic_catalog_capability_requirement import AIcCatalogCapabilityRequirement
from .aic_catalog_persistent_schema import AIcCatalogPersistentSchema

@dataclass(frozen=True, slots=True)
class AIcCatalogRelease:
    version: int
    provides: tuple[AIcCatalogCapabilityOffer, ...] = ()
    requires: tuple[AIcCatalogCapabilityRequirement, ...] = ()
    entitlement_licensing_scopes: tuple[AIcEntitlementLicensingScopeDescriptor, ...] = ()
    provided_capability_entitlements: tuple[AIcCapabilityEntitlementDescriptor, ...] = ()
    persistent_schemas: tuple[AIcCatalogPersistentSchema, ...] = ()
    artifacts: tuple[AIcCatalogArtifact, ...] = ()
    published_at: str | None = None
    release_notes_url: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("catalog release version must be >= 1")
        licensing_scope_types = [item.type for item in self.entitlement_licensing_scopes]
        if len(licensing_scope_types) != len(set(licensing_scope_types)):
            raise ValueError("catalog entitlement licensing scope declarations must be unique by type")
        declared_licensing_scope_types = set(licensing_scope_types)
        referenced_licensing_scope_types = {
            scope_type
            for entitlement in self.provided_capability_entitlements
            for permission in entitlement.permissions
            for scope_type in permission.possible_licensing_scope_types
        }
        undeclared = sorted(referenced_licensing_scope_types - declared_licensing_scope_types)
        if undeclared:
            raise ValueError(
                "catalog capability entitlement declarations reference undeclared entitlement licensing scopes: "
                f"{undeclared!r}"
            )
        artifact_ids = [artifact.id for artifact in self.artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("catalog artifact ids must be unique inside one release")
        requirement_ids = [requirement.id for requirement in self.requires]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("catalog requirement ids must be unique inside one release")
        schema_ids = [item.identity for item in self.persistent_schemas]
        if len(schema_ids) != len(set(schema_ids)):
            raise ValueError("catalog persistent schemas must be unique by kind/provider-or-entity identity")
