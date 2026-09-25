from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..capability.api import AIcProvidedCapability, AInConsumerCardinality
from ..instances.api import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness.api import AIcReadinessRequirementDescriptor

from .aic_capability_entitlement_descriptor import AIcCapabilityEntitlementDescriptor
from .aic_data_entity_support_descriptor import AIcDataEntitySupportDescriptor
from .aic_entitlement_licensing_scope_descriptor import AIcEntitlementLicensingScopeDescriptor
from .aic_lifecycle_hooks_descriptor import AIcLifecycleHooksDescriptor
from .aic_persisted_schema_descriptor import AIcPersistedSchemaDescriptor
from .aic_provider_definition_descriptor import AIcProviderDefinitionDescriptor

@dataclass(frozen=True, slots=True)
class AIcComponentDescriptor:
    id: str
    version: int
    capability_providers: tuple[AIcProviderDefinitionDescriptor, ...] = ()
    capability_group_resources: tuple[str, ...] = ()
    contract_resources: tuple[str, ...] = ()
    component_configuration_schema: AIcPersistedSchemaDescriptor | None = None
    entitlement_licensing_scopes: tuple[AIcEntitlementLicensingScopeDescriptor, ...] = ()
    provided_capability_entitlements: tuple[AIcCapabilityEntitlementDescriptor, ...] = ()
    data_entity_support: tuple[AIcDataEntitySupportDescriptor, ...] = ()
    lifecycle: AIcLifecycleHooksDescriptor = AIcLifecycleHooksDescriptor()
    metadata: Mapping[str, object] = field(default_factory=dict)
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if self.component_configuration_schema is not None and self.component_configuration_schema.resource_name is None:
            raise ValueError("component configuration schema requires a resource_name for validation")
        if not self.id or self.version < 1:
            raise ValueError("component id must not be empty and version must be >= 1")
        provider_ids = [provider.id for provider in self.capability_providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("capability provider definition ids must be unique inside a component descriptor")
        licensing_scope_types = [item.type for item in self.entitlement_licensing_scopes]
        if len(licensing_scope_types) != len(set(licensing_scope_types)):
            raise ValueError("entitlement licensing scope declarations must be unique by type")
        declared_licensing_scope_types = set(licensing_scope_types)
        referenced_licensing_scope_types = {
            scope_type
            for entitlement in self.provided_capability_entitlements
            for permission in entitlement.permissions
            for scope_type in permission.possible_licensing_scope_types
        }
        undeclared_licensing_scope_types = sorted(referenced_licensing_scope_types - declared_licensing_scope_types)
        if undeclared_licensing_scope_types:
            raise ValueError(
                "capability permission declarations reference undeclared entitlement licensing scopes: "
                f"{undeclared_licensing_scope_types!r}"
            )
        entitlement_keys = [(item.capability_id, item.capability_version) for item in self.provided_capability_entitlements]
        if len(entitlement_keys) != len(set(entitlement_keys)):
            raise ValueError("capability entitlement declarations must be unique by capability id/version")
        provided = {
            (capability.id, version)
            for provider in self.capability_providers
            for capability in provider.capabilities
            for version in capability.versions
        }
        unknown = [key for key in entitlement_keys if key not in provided]
        if unknown:
            raise ValueError(f"capability entitlement declarations reference capabilities not provided by component: {unknown!r}")
        data_entity_schema_ids = [item.schema_id for item in self.data_entity_support]
        if len(data_entity_schema_ids) != len(set(data_entity_schema_ids)):
            raise ValueError("data entity support declarations must be unique by schema_id")

    def provider(self, provider_definition_id: str) -> AIcProviderDefinitionDescriptor:
        for provider in self.capability_providers:
            if provider.id == provider_definition_id:
                return provider
        raise KeyError(provider_definition_id)

    def capability_entitlement(self, capability_id: str, capability_version: int) -> AIcCapabilityEntitlementDescriptor | None:
        for item in self.provided_capability_entitlements:
            if item.capability_id == capability_id and item.capability_version == capability_version:
                return item
        return None
