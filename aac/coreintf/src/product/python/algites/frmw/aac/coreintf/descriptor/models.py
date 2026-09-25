from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from ..presentation import AIcDisplayText

from ..capability import AIcProvidedCapability, AInConsumerCardinality
from ..instances import AInProviderAccessMode
from ..interaction_types import AInStateResultDeliveryMode
from ..readiness import AIcReadinessRequirementDescriptor


class AInComponentOrigin(str, Enum):
    BUILTIN = "BUILTIN"
    PACKAGE = "PACKAGE"


class AInProviderRuntimeProfile(str, Enum):
    IN_PROCESS = "IN_PROCESS"
    PROCESS = "PROCESS"
    SUBINTERPRETER = "SUBINTERPRETER"


class AInDataEntityAccess(str, Enum):
    READ = "READ"
    WRITE = "WRITE"


@dataclass(frozen=True, slots=True)
class AIcSchemaMigrationStepDescriptor:
    from_version: int
    to_version: int
    migrator_id: str

    def __post_init__(self) -> None:
        if self.from_version < 1 or self.to_version < 1:
            raise ValueError("schema migration versions must be >= 1")
        if self.from_version == self.to_version:
            raise ValueError("schema migration must change the schema version")
        if not self.migrator_id:
            raise ValueError("schema migration migrator_id must not be empty")


@dataclass(frozen=True, slots=True)
class AIcPersistedSchemaDescriptor:
    schema_id: str
    write_version: int
    readable_versions: tuple[int, ...]
    migrations: tuple[AIcSchemaMigrationStepDescriptor, ...] = ()
    resource_name: str | None = None

    def __post_init__(self) -> None:
        if not self.schema_id or self.write_version < 1:
            raise ValueError("persisted schema requires schema_id and write_version >= 1")
        if not self.readable_versions or any(v < 1 for v in self.readable_versions):
            raise ValueError("persisted schema must declare readable_versions >= 1")
        if len(self.readable_versions) != len(set(self.readable_versions)):
            raise ValueError("persisted schema readable_versions must be unique")
        if self.write_version not in self.readable_versions:
            raise ValueError("persisted schema write_version must also be readable")
        if self.resource_name is not None and not self.resource_name:
            raise ValueError("persisted schema resource_name must not be empty")
        identities = [(m.from_version, m.to_version) for m in self.migrations]
        if len(identities) != len(set(identities)):
            raise ValueError("persisted schema migration from/to pairs must be unique")



@dataclass(frozen=True, slots=True)
class AIcProviderRuntimeDescriptor:
    profile: AInProviderRuntimeProfile = AInProviderRuntimeProfile.IN_PROCESS
    command: tuple[str, ...] = ()
    cwd: str | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("runtime timeout_seconds must be > 0")
        if self.profile is not AInProviderRuntimeProfile.PROCESS and self.command:
            raise ValueError("runtime command is only valid for PROCESS profile")


@dataclass(frozen=True, slots=True)
class AIcInitialProviderInstanceDescriptor:
    name: str = "default"
    configuration: Mapping[str, object] = field(default_factory=dict)
    access_mode: AInProviderAccessMode = AInProviderAccessMode.READ_WRITE


@dataclass(frozen=True, slots=True)
class AIcConsumerRequirementDescriptor:
    id: str
    capability_id: str
    versions: tuple[int, ...]
    cardinality: AInConsumerCardinality = AInConsumerCardinality.SINGLE
    mandatory: bool = True
    requested_authorizations: tuple[str, ...] = ()
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.capability_id:
            raise ValueError("consumer requirement id/capability must not be empty")
        if any(version < 1 for version in self.versions):
            raise ValueError("consumer requirement versions must be >= 1")
        if len(self.versions) != len(set(self.versions)):
            raise ValueError("consumer requirement versions must be unique")
        if len(self.requested_authorizations) != len(set(self.requested_authorizations)):
            raise ValueError("requested authorization permissions must be unique")




@dataclass(frozen=True, slots=True)
class AIcOperationParameterEnumValueDescriptor:
    value: object
    name: AIcDisplayText
    description: AIcDisplayText | None = None


@dataclass(frozen=True, slots=True)
class AIcOperationParameterDefinitionDescriptor:
    id: str
    name: AIcDisplayText
    description: AIcDisplayText
    value_schema: Mapping[str, object]
    enum_values: tuple[AIcOperationParameterEnumValueDescriptor, ...] = ()
    required: bool = False
    default: object | None = None
    has_default: bool = False
    component_configurable: bool = False
    instance_configurable: bool = False
    invocation_overridable: bool = False

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("operation parameter id must not be empty")
        if not self.value_schema:
            raise ValueError("operation parameter value_schema must not be empty")
        enum_values = [item.value for item in self.enum_values]
        if len(enum_values) != len({repr(value) for value in enum_values}):
            raise ValueError("operation parameter enum values must be unique")


@dataclass(frozen=True, slots=True)
class AIcCapabilityProviderOperationInteractionDescriptor:
    supported_state_result_delivery_modes: tuple[AInStateResultDeliveryMode, ...] = (
        AInStateResultDeliveryMode.ON_DEMAND_COMPLETE,
    )
    progress_reporting: bool = False
    cancellation: bool = False
    detail_level: bool = False
    reporting_interval: bool = False

    def __post_init__(self) -> None:
        if not self.supported_state_result_delivery_modes:
            raise ValueError("provider operation interaction must declare at least one state-result delivery mode")
        if len(self.supported_state_result_delivery_modes) != len(set(self.supported_state_result_delivery_modes)):
            raise ValueError("provider operation interaction state-result delivery modes must be unique")
        if AInStateResultDeliveryMode.ON_DEMAND_COMPLETE not in self.supported_state_result_delivery_modes:
            raise ValueError("provider operation interaction must support ON_DEMAND_COMPLETE")


@dataclass(frozen=True, slots=True)
class AIcCapabilityProviderOperationDescriptor:
    capability_id: str
    capability_version: int
    operation_id: str
    interaction: AIcCapabilityProviderOperationInteractionDescriptor
    parameters: tuple[AIcOperationParameterDefinitionDescriptor, ...] = ()

    def __post_init__(self) -> None:
        if not self.capability_id or self.capability_version < 1 or not self.operation_id:
            raise ValueError("provider operation requires capability id/version and operation id")
        ids = [item.id for item in self.parameters]
        if len(ids) != len(set(ids)):
            raise ValueError("operation parameter ids must be unique inside one provider operation")

    def parameter(self, parameter_id: str) -> AIcOperationParameterDefinitionDescriptor:
        for item in self.parameters:
            if item.id == parameter_id:
                return item
        raise KeyError(parameter_id)




@dataclass(frozen=True, slots=True)
class AIcProviderImplementationClassDescriptor:
    technology_kind: str
    class_name: str

    def __post_init__(self) -> None:
        if not self.technology_kind.strip():
            raise ValueError("provider implementation technology_kind must not be empty")
        if not self.class_name.strip():
            raise ValueError("provider implementation class_name must not be empty")

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


@dataclass(frozen=True, slots=True)
class AIcEntitlementLicensingScopeDescriptor:
    type: str
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = self.type.strip()
        if not normalized:
            raise ValueError("entitlement licensing scope type must not be empty")
        object.__setattr__(self, "type", normalized)


@dataclass(frozen=True, slots=True)
class AIcPermissionDescriptor:
    id: str
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    possible_licensing_scope_types: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("permission id must not be empty")
        if len(self.possible_licensing_scope_types) != len(set(self.possible_licensing_scope_types)):
            raise ValueError("possible entitlement licensing scope types must be unique")

    @property
    def implicit(self) -> bool:
        """Permission is included/scope-free when no external entitlement licensing scope is possible."""
        return not self.possible_licensing_scope_types


@dataclass(frozen=True, slots=True)
class AIcCapabilityEntitlementDescriptor:
    capability_id: str
    capability_version: int
    permissions: tuple[AIcPermissionDescriptor, ...]
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.capability_id or self.capability_version < 1:
            raise ValueError("capability entitlement requires capability id/version")
        permission_ids = [permission.id for permission in self.permissions]
        if len(permission_ids) != len(set(permission_ids)):
            raise ValueError("permission ids must be unique inside one capability-version entitlement declaration")

    def permission(self, permission_id: str) -> AIcPermissionDescriptor:
        for permission in self.permissions:
            if permission.id == permission_id:
                return permission
        raise KeyError(permission_id)


@dataclass(frozen=True, slots=True)
class AIcDataEntityRequirementDescriptor:
    schema_id: str
    access: tuple[AInDataEntityAccess, ...] = (AInDataEntityAccess.READ,)
    readable_versions: tuple[int, ...] = ()
    writable_versions: tuple[int, ...] = ()
    required: bool = True

    def __post_init__(self) -> None:
        if not self.schema_id:
            raise ValueError("data entity requirement schema_id must not be empty")
        if not self.access or len(self.access) != len(set(self.access)):
            raise ValueError("data entity requirement access entries must be non-empty and unique")
        if any(version < 1 for version in self.readable_versions + self.writable_versions):
            raise ValueError("data entity requirement versions must be >= 1")
        if len(self.readable_versions) != len(set(self.readable_versions)):
            raise ValueError("data entity requirement readable_versions must be unique")
        if len(self.writable_versions) != len(set(self.writable_versions)):
            raise ValueError("data entity requirement writable_versions must be unique")
        if AInDataEntityAccess.READ in self.access and not self.readable_versions:
            raise ValueError("READ data entity requirement requires readable_versions")
        if AInDataEntityAccess.WRITE in self.access and not self.writable_versions:
            raise ValueError("WRITE data entity requirement requires writable_versions")


@dataclass(frozen=True, slots=True)
class AIcDataEntitySupportDescriptor:
    schema_id: str
    readable_versions: tuple[int, ...] = ()
    writable_versions: tuple[int, ...] = ()
    preferred_write_version: int | None = None
    migrations: tuple[AIcSchemaMigrationStepDescriptor, ...] = ()
    data_entity_requirements: tuple[AIcDataEntityRequirementDescriptor, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.schema_id:
            raise ValueError("data entity support schema_id must not be empty")
        if not self.readable_versions and not self.writable_versions:
            raise ValueError("data entity support must declare at least one readable or writable version")
        if any(version < 1 for version in self.readable_versions + self.writable_versions):
            raise ValueError("data entity support versions must be >= 1")
        if len(self.readable_versions) != len(set(self.readable_versions)):
            raise ValueError("data entity support readable_versions must be unique")
        if len(self.writable_versions) != len(set(self.writable_versions)):
            raise ValueError("data entity support writable_versions must be unique")
        if self.writable_versions:
            if self.preferred_write_version is None:
                raise ValueError("data entity support with writable_versions requires preferred_write_version")
            if self.preferred_write_version not in self.writable_versions:
                raise ValueError("preferred_write_version must be one of writable_versions")
        elif self.preferred_write_version is not None:
            raise ValueError("read-only data entity support must not declare preferred_write_version")
        migration_pairs = [(item.from_version, item.to_version) for item in self.migrations]
        if len(migration_pairs) != len(set(migration_pairs)):
            raise ValueError("data entity migration from/to pairs must be unique")
        requirement_ids = [item.schema_id for item in self.data_entity_requirements]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("data entity requirements must be unique by schema_id")

    def can_read(self, schema_version: int) -> bool:
        return schema_version in self.readable_versions

    def can_write(self, schema_version: int) -> bool:
        return schema_version in self.writable_versions


@dataclass(frozen=True, slots=True)
class AIcLifecycleHooksDescriptor:
    provision: str | None = None
    validate: str | None = None
    unprovision: str | None = None


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
