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

class AIcConfigurationProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, AIiConfigurationProvider] = {}

    def register(self, configuration_provider_id: str, provider: AIiConfigurationProvider) -> None:
        if not configuration_provider_id:
            raise ValueError("configuration_provider_id must not be empty")
        self._providers[configuration_provider_id] = provider

    def contains(self, configuration_provider_id: str) -> bool:
        return configuration_provider_id in self._providers

    def get(self, configuration_provider_id: str) -> AIiConfigurationProvider:
        return self._providers[configuration_provider_id]
