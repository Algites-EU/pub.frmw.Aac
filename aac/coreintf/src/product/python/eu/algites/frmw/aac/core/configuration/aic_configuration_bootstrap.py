from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_profile import AIcConfigurationProfile
from .aic_configuration_profile_source_registration import AIcConfigurationProfileSourceRegistration
from .aic_configuration_provider_registration import AIcConfigurationProviderRegistration
from .aic_configuration_scope_resolver_registration import AIcConfigurationScopeResolverRegistration
from .ain_workspace_configuration_profile_policy import AInWorkspaceConfigurationProfilePolicy

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
