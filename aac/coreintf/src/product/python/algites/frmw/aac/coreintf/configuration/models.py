from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from ..context import AIcConfigurationScope
from ..presentation import AIcDisplayText


class AInConfigurationPolicyMode(str, Enum):
    LOCK = "LOCK"
    MIN = "MIN"
    MAX = "MAX"
    IN_SET = "IN_SET"
    NOT_IN_SET = "NOT_IN_SET"
    DEFAULT = "DEFAULT"


class AInConfigurationValueSourceKind(str, Enum):
    EXPLICIT = "EXPLICIT"
    POLICY_LOCK = "POLICY_LOCK"
    POLICY_DEFAULT = "POLICY_DEFAULT"
    SCHEMA_DEFAULT = "SCHEMA_DEFAULT"
    UNDEFINED = "UNDEFINED"


class AInWorkspaceConfigurationProfilePolicy(str, Enum):
    FORBIDDEN = "FORBIDDEN"
    ALLOWED = "ALLOWED"
    ALLOWED_IF_SIGNED = "ALLOWED_IF_SIGNED"


class AInConfigurationTargetKind(str, Enum):
    COMPONENT = "COMPONENT"
    PROVIDER_INSTANCE = "PROVIDER_INSTANCE"


class AInConfigurationProviderCapability(str, Enum):
    READ = "READ"
    WRITE_VALUE = "WRITE_VALUE"
    DELETE_VALUE = "DELETE_VALUE"
    WRITE_POLICY = "WRITE_POLICY"
    DELETE_POLICY = "DELETE_POLICY"
    ATOMIC_CHANGE_SET = "ATOMIC_CHANGE_SET"


class AInConfigurationMutationOperation(str, Enum):
    SET_VALUE = "SET_VALUE"
    DELETE_VALUE = "DELETE_VALUE"
    SET_POLICY = "SET_POLICY"
    DELETE_POLICY = "DELETE_POLICY"


@dataclass(frozen=True, slots=True)
class AIcConfigurationTarget:
    kind: AInConfigurationTargetKind
    component_id: str
    provider_instance_id: str | None = None

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("configuration target component_id must not be empty")
        if self.kind is AInConfigurationTargetKind.COMPONENT:
            if self.provider_instance_id is not None:
                raise ValueError("COMPONENT configuration target must not carry provider_instance_id")
        elif self.kind is AInConfigurationTargetKind.PROVIDER_INSTANCE:
            if not self.provider_instance_id:
                raise ValueError("PROVIDER_INSTANCE configuration target requires provider_instance_id")

    @property
    def key(self) -> str:
        if self.kind is AInConfigurationTargetKind.COMPONENT:
            return f"COMPONENT:{self.component_id}"
        return f"PROVIDER_INSTANCE:{self.component_id}:{self.provider_instance_id}"


@dataclass(frozen=True, slots=True)
class AIcConfigurationPolicy:
    mode: AInConfigurationPolicyMode
    value: object


@dataclass(frozen=True, slots=True)
class AIcConfigurationContribution:
    property_id: str
    value: object | None = None
    has_value: bool = False
    policy_modes: tuple[AIcConfigurationPolicy, ...] = ()
    configuration_schema_id: str | None = None
    configuration_schema_version: int | None = None
    written_by_component_version: int | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.property_id:
            raise ValueError("configuration contribution property_id must not be empty")
        if not self.has_value and self.value is not None:
            raise ValueError("value requires has_value=True so explicit null remains representable")
        if self.configuration_schema_version is not None and self.configuration_schema_version < 1:
            raise ValueError("configuration_schema_version must be >= 1")
        if self.written_by_component_version is not None and self.written_by_component_version < 1:
            raise ValueError("written_by_component_version must be >= 1")


@dataclass(frozen=True, slots=True)
class AIcConfigurationChange:
    property_id: str
    operation: AInConfigurationMutationOperation
    value: object | None = None
    has_value: bool = False
    policy_modes: tuple[AIcConfigurationPolicy, ...] = ()

    def __post_init__(self) -> None:
        if not self.property_id:
            raise ValueError("configuration change property_id must not be empty")
        if self.operation is AInConfigurationMutationOperation.SET_VALUE:
            if not self.has_value:
                raise ValueError("SET_VALUE requires has_value=True so explicit null remains representable")
            if self.policy_modes:
                raise ValueError("SET_VALUE must not carry policy_modes")
        elif self.operation is AInConfigurationMutationOperation.SET_POLICY:
            if not self.policy_modes:
                raise ValueError("SET_POLICY requires at least one policy mode")
            if self.has_value or self.value is not None:
                raise ValueError("SET_POLICY must not carry a value")
        else:
            if self.has_value or self.value is not None or self.policy_modes:
                raise ValueError(f"{self.operation.value} must not carry value or policy_modes")


@dataclass(frozen=True, slots=True)
class AIcConfigurationChangeSet:
    configuration_scope: AIcConfigurationScope
    configuration_provider_id: str
    configuration_target: AIcConfigurationTarget
    changes: tuple[AIcConfigurationChange, ...]
    expected_record_revision: str | int | None = None
    configuration_schema_id: str | None = None
    configuration_schema_version: int | None = None
    written_by_component_version: int | None = None
    actor_context: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.configuration_provider_id:
            raise ValueError("configuration_provider_id must not be empty")
        if not self.changes:
            raise ValueError("configuration change-set must contain at least one change")
        schema_fields = (self.configuration_schema_id, self.configuration_schema_version, self.written_by_component_version)
        if any(value is not None for value in schema_fields) and not all(value is not None for value in schema_fields):
            raise ValueError("configuration schema id/version and written_by_component_version must be supplied together")
        if self.configuration_schema_version is not None and self.configuration_schema_version < 1:
            raise ValueError("configuration_schema_version must be >= 1")
        if self.written_by_component_version is not None and self.written_by_component_version < 1:
            raise ValueError("written_by_component_version must be >= 1")
        identities = [(c.property_id, c.operation.value) for c in self.changes]
        if len(identities) != len(set(identities)):
            raise ValueError("configuration change-set contains duplicate property/operation changes")


@dataclass(frozen=True, slots=True)
class AIcConfigurationMutationResult:
    record_revision: str | int | None = None
    changed_property_ids: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AIcConfigurationProviderBinding:
    configuration_provider_id: str
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.configuration_provider_id:
            raise ValueError("configuration_provider_id must not be empty")


@dataclass(frozen=True, slots=True)
class AIcConfigurationScopeDefinition:
    id: str
    configuration_scope_type: str
    configuration_scope_resolver_id: str
    configuration_providers: tuple[AIcConfigurationProviderBinding, ...] = ()
    policy_authority: bool = True
    mandatory: bool = False
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("configuration-scope definition id must not be empty")
        if not self.configuration_scope_type:
            raise ValueError("configuration_scope_type must not be empty")
        if not self.configuration_scope_resolver_id:
            raise ValueError("configuration_scope_resolver_id must not be empty")
        provider_ids = [item.configuration_provider_id for item in self.configuration_providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("configuration-provider bindings must be unique inside one configuration-scope definition")


@dataclass(frozen=True, slots=True)
class AIcConfigurationProfile:
    id: str
    version: int
    configuration_scopes: tuple[AIcConfigurationScopeDefinition, ...]
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("configuration profile id must not be empty")
        if self.version < 1:
            raise ValueError("configuration profile version must be >= 1")
        if not self.configuration_scopes:
            raise ValueError("configuration profile must define at least one configuration-scope")
        definition_ids = [item.id for item in self.configuration_scopes]
        if len(definition_ids) != len(set(definition_ids)):
            raise ValueError("configuration-scope definition ids must be unique inside a profile")


@dataclass(frozen=True, slots=True)
class AIcConfigurationProviderRegistration:
    id: str
    type: str
    settings: Mapping[str, object] = field(default_factory=dict)
    authentication_profile_id: str | None = None
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.type:
            raise ValueError("configuration-provider registration id and type must not be empty")


@dataclass(frozen=True, slots=True)
class AIcConfigurationProfileSourceRegistration:
    id: str
    uri: str
    authentication_profile_id: str | None = None
    required: bool = True
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.uri:
            raise ValueError("configuration-profile source id/uri must not be empty")


@dataclass(frozen=True, slots=True)
class AIcConfigurationScopeResolverRegistration:
    id: str
    type: str
    settings: Mapping[str, object] = field(default_factory=dict)
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.type:
            raise ValueError("configuration-scope resolver registration id and type must not be empty")


@dataclass(frozen=True, slots=True)
class AIcConfigurationBootstrap:
    schema_version: int
    default_configuration_profile_id: str
    configuration_profiles: tuple[AIcConfigurationProfile, ...]
    configuration_providers: tuple[AIcConfigurationProviderRegistration, ...] = ()
    configuration_scope_resolvers: tuple[AIcConfigurationScopeResolverRegistration, ...] = ()
    configuration_profile_sources: tuple[AIcConfigurationProfileSourceRegistration, ...] = ()
    workspace_configuration_profiles: AInWorkspaceConfigurationProfilePolicy = AInWorkspaceConfigurationProfilePolicy.FORBIDDEN
    mandatory_configuration_scope_definition_ids: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version < 1:
            raise ValueError("configuration bootstrap schema_version must be >= 1")
        profiles = {profile.id: profile for profile in self.configuration_profiles}
        if len(profiles) != len(self.configuration_profiles):
            raise ValueError("configuration profile ids must be unique")
        if self.default_configuration_profile_id not in profiles and not self.configuration_profile_sources:
            raise ValueError("default_configuration_profile_id must reference a configured or external profile")
        provider_ids = [item.id for item in self.configuration_providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("configuration-provider registration ids must be unique")
        resolver_ids = [item.id for item in self.configuration_scope_resolvers]
        profile_source_ids = [item.id for item in self.configuration_profile_sources]
        if len(profile_source_ids) != len(set(profile_source_ids)):
            raise ValueError("configuration-profile source ids must be unique")
        if len(resolver_ids) != len(set(resolver_ids)):
            raise ValueError("configuration-scope resolver registration ids must be unique")
        provider_id_set = set(provider_ids)
        resolver_id_set = set(resolver_ids)
        for profile in self.configuration_profiles:
            for definition in profile.configuration_scopes:
                if definition.configuration_scope_resolver_id not in resolver_id_set:
                    raise ValueError(
                        f"configuration profile {profile.id!r} references unregistered configuration-scope resolver "
                        f"{definition.configuration_scope_resolver_id!r}"
                    )
                for binding in definition.configuration_providers:
                    if binding.configuration_provider_id not in provider_id_set:
                        raise ValueError(
                            f"configuration profile {profile.id!r} references unregistered configuration-provider "
                            f"{binding.configuration_provider_id!r}"
                        )

    def profile(self, profile_id: str | None = None) -> AIcConfigurationProfile:
        target = profile_id or self.default_configuration_profile_id
        for profile in self.configuration_profiles:
            if profile.id == target:
                return profile
        raise KeyError(target)


@dataclass(frozen=True, slots=True)
class AIcConfigurationProviderSnapshot:
    configuration_scope: AIcConfigurationScope
    configuration_target: AIcConfigurationTarget
    record_revision: str | int | None
    payload: "AIcConfigurationPersistedPayload"


@dataclass(frozen=True, slots=True)
class AIcConfigurationProviderAccess:
    configuration_scope: AIcConfigurationScope
    configuration_provider_id: str
    configuration_target: AIcConfigurationTarget
    technical_capabilities: tuple[AInConfigurationProviderCapability, ...]
    authorized_capabilities: tuple[AInConfigurationProviderCapability, ...]
    diagnostics: tuple[str, ...] = ()

    def allows(self, capability: AInConfigurationProviderCapability) -> bool:
        return capability in self.authorized_capabilities


@dataclass(frozen=True, slots=True)
class AIcConfigurationProviderRequest:
    configuration_target: AIcConfigurationTarget
    configuration_scope: AIcConfigurationScope
    context: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AIcConfigurationScopeResolutionRequest:
    configuration_scope_type: str
    definition_id: str
    context: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AIcResolvedConfigurationScope:
    definition_id: str
    configuration_scope: AIcConfigurationScope
    configuration_providers: tuple[AIcConfigurationProviderBinding, ...]
    policy_authority: bool = True


@dataclass(frozen=True, slots=True)
class AIcConfigurationContributionProvenance:
    configuration_scope: AIcConfigurationScope
    configuration_provider_id: str
    configuration_provider_priority: int
    provider_record_revision: str | int | None = None


@dataclass(frozen=True, slots=True)
class AIcEffectiveConfigurationPolicy:
    lock: object | None = None
    has_lock: bool = False
    minimum: object | None = None
    maximum: object | None = None
    in_set: tuple[object, ...] | None = None
    not_in_set: tuple[object, ...] = ()
    provenance: tuple[tuple[AIcConfigurationPolicy, AIcConfigurationContributionProvenance], ...] = ()


@dataclass(frozen=True, slots=True)
class AIcEffectiveConfigurationValue:
    property_id: str
    value: object | None
    source_kind: AInConfigurationValueSourceKind
    provenance: AIcConfigurationContributionProvenance | None
    effective_policy: AIcEffectiveConfigurationPolicy
    shadowed_provenance: tuple[AIcConfigurationContributionProvenance, ...] = ()


@dataclass(frozen=True, slots=True)
class AIcEffectiveConfiguration:
    configuration_target: AIcConfigurationTarget
    values: Mapping[str, AIcEffectiveConfigurationValue]
    configuration_scopes: tuple[AIcResolvedConfigurationScope, ...]
    diagnostics: tuple[str, ...] = ()

    def plain_values(self) -> dict[str, object | None]:
        return {key: value.value for key, value in self.values.items() if value.source_kind is not AInConfigurationValueSourceKind.UNDEFINED}

@dataclass(frozen=True, slots=True)
class AIcConfigurationPersistedPayload:
    configuration_target: AIcConfigurationTarget
    configuration_schema_id: str
    configuration_schema_version: int
    written_by_component_version: int
    values: Mapping[str, object] = field(default_factory=dict)
    policies: Mapping[str, tuple[AIcConfigurationPolicy, ...]] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.configuration_schema_id or self.configuration_schema_version < 1:
            raise ValueError("persisted configuration payload requires schema id/version >= 1")
        if self.written_by_component_version < 1:
            raise ValueError("written_by_component_version must be >= 1")


@dataclass(frozen=True, slots=True)
class AIcConfigurationMigrationRequest:
    source: AIcConfigurationPersistedPayload
    target_configuration_schema_version: int

    def __post_init__(self) -> None:
        if self.target_configuration_schema_version < 1:
            raise ValueError("target configuration schema version must be >= 1")


@dataclass(frozen=True, slots=True)
class AIcConfigurationMigrationResult:
    configuration_schema_id: str
    configuration_schema_version: int
    values: Mapping[str, object]
    policies: Mapping[str, tuple[AIcConfigurationPolicy, ...]] = field(default_factory=dict)
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.configuration_schema_id or self.configuration_schema_version < 1:
            raise ValueError("configuration migration result requires schema id/version >= 1")
