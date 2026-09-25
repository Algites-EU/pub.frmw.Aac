from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Mapping
from eu.algites.frmw.aac.core.configuration.api import (
    AInConfigurationPolicyMode,
    AInConfigurationProviderCapability,
    AInConfigurationValueSourceKind,
    AIcConfigurationChangeSet,
    AIcConfigurationProviderAccess,
    AIcConfigurationContribution,
    AIcConfigurationMutationResult,
    AIcConfigurationTarget,
    AIcConfigurationContributionProvenance,
    AIcConfigurationProfile,
    AIcConfigurationProviderRequest,
    AIcConfigurationScopeResolutionRequest,
    AIcEffectiveConfiguration,
    AIcEffectiveConfigurationPolicy,
    AIcEffectiveConfigurationValue,
    AIcResolvedConfigurationScope,
    AIiConfigurationMutationAuthorizer,
    AIiConfigurationProvider,
    AIiConfigurationScopeResolver,
)
from eu.algites.frmw.aac.core.context.api import AIcConfigurationScope
from eu.algites.frmw.aac.core.migration.api import AInSchemaRuntimeInterpretation
from eu.algites.frmw.aac.core.persistence.api import AInPersistenceCapability
from eu.algites.frmw.aac.core.implementation.errors import AIxConfigurationConflictError, AIxConfigurationPolicyError

class AIcConfigurationScopeResolverRegistry:
    def __init__(self) -> None:
        self._resolvers: dict[str, AIiConfigurationScopeResolver] = {}

    def register(self, configuration_scope_resolver_id: str, resolver: AIiConfigurationScopeResolver) -> None:
        if not configuration_scope_resolver_id:
            raise ValueError("configuration_scope_resolver_id must not be empty")
        self._resolvers[configuration_scope_resolver_id] = resolver

    def contains(self, configuration_scope_resolver_id: str) -> bool:
        return configuration_scope_resolver_id in self._resolvers

    def get(self, configuration_scope_resolver_id: str) -> AIiConfigurationScopeResolver:
        return self._resolvers[configuration_scope_resolver_id]
