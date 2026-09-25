from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..capability.api import AIcProvidedCapability, AInConsumerCardinality
from ..instances.api import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness.api import AIcReadinessRequirementDescriptor

from .aic_capability_provider_operation_descriptor import AIcCapabilityProviderOperationDescriptor
from .aic_consumer_requirement_descriptor import AIcConsumerRequirementDescriptor
from .aic_initial_provider_instance_descriptor import AIcInitialProviderInstanceDescriptor
from .aic_persisted_schema_descriptor import AIcPersistedSchemaDescriptor
from .aic_provider_implementation_class_descriptor import AIcProviderImplementationClassDescriptor
from .aic_provider_runtime_descriptor import AIcProviderRuntimeDescriptor

@dataclass(frozen=True, slots=True)
class AIcProviderDefinitionDescriptor:
    id: str
    capabilities: tuple[AIcProvidedCapability, ...]
    implementation_classes: tuple[AIcProviderImplementationClassDescriptor, ...]
    configuration_schema: AIcPersistedSchemaDescriptor | None = None
    initial_instances: tuple[AIcInitialProviderInstanceDescriptor, ...] = ()
    requirements: tuple[AIcConsumerRequirementDescriptor, ...] = ()
    operations: tuple[AIcCapabilityProviderOperationDescriptor, ...] = ()
    readiness_requirements: tuple[AIcReadinessRequirementDescriptor, ...] = ()
    runtime_factory_class: str | None = None
    runtime: AIcProviderRuntimeDescriptor = AIcProviderRuntimeDescriptor()
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if self.configuration_schema is not None and self.configuration_schema.resource_name is None:
            raise ValueError("provider configuration schema requires a resource_name for validation")
        if not self.id:
            raise ValueError("provider definition id must not be empty")
        if not self.capabilities:
            raise ValueError("provider must provide at least one capability")
        if not self.implementation_classes:
            raise ValueError("provider must declare at least one technology implementation class")
        technology_kinds = [item.technology_kind for item in self.implementation_classes]
        if len(technology_kinds) != len(set(technology_kinds)):
            raise ValueError("provider implementation technology kinds must be unique")
        capability_ids = [capability.id for capability in self.capabilities]
        if len(capability_ids) != len(set(capability_ids)):
            raise ValueError("provider capability ids must be unique")
        operation_keys = [(item.capability_id, item.capability_version, item.operation_id) for item in self.operations]
        if len(operation_keys) != len(set(operation_keys)):
            raise ValueError("provider operation descriptors must be unique by capability/version/operation")
        for item in self.operations:
            capability = self.capability(item.capability_id)
            if item.capability_version not in capability.versions:
                raise ValueError("provider operation descriptor references an unprovided capability version")
        requirement_ids = [requirement.id for requirement in self.requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("consumer requirement ids must be unique inside a capability provider definition")
        readiness_ids = [requirement.id for requirement in self.readiness_requirements]
        if len(readiness_ids) != len(set(readiness_ids)):
            raise ValueError("readiness requirement ids must be unique inside a capability provider definition")


    def implementation_class_for(self, technology_kind: str) -> str:
        for implementation in self.implementation_classes:
            if implementation.technology_kind == technology_kind:
                return implementation.class_name
        raise KeyError(technology_kind)

    def capability(self, capability_id: str) -> AIcProvidedCapability:
        for capability in self.capabilities:
            if capability.id == capability_id:
                return capability
        raise KeyError(capability_id)

    def supports_capability(self, capability_id: str) -> bool:
        return any(capability.id == capability_id for capability in self.capabilities)

    def operation_definition(
        self, capability_id: str, capability_version: int, operation_id: str
    ) -> AIcCapabilityProviderOperationDescriptor | None:
        for item in self.operations:
            if (item.capability_id, item.capability_version, item.operation_id) == (capability_id, capability_version, operation_id):
                return item
        return None

    def operation_parameter_definition(
        self, capability_id: str, capability_version: int, operation_id: str
    ) -> AIcCapabilityProviderOperationDescriptor | None:
        return self.operation_definition(capability_id, capability_version, operation_id)
