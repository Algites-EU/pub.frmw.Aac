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

class AIcStaticConfigurationProvider(AIiConfigurationProvider):
    """In-memory read-only provider useful for bootstrap defaults/tests."""

    def __init__(self, contributions: Mapping[object, Iterable[AIcConfigurationContribution]]) -> None:
        self._contributions = {key: tuple(value) for key, value in contributions.items()}

    def contributions(self, request: AIcConfigurationProviderRequest) -> tuple[AIcConfigurationContribution, ...]:
        exact = (request.configuration_scope.key, request.configuration_target.key)
        if exact in self._contributions:
            return self._contributions[exact]
        # Scope-only entries are convenient for defaults/tests and apply to any target.
        return self._contributions.get(request.configuration_scope.key, ())
