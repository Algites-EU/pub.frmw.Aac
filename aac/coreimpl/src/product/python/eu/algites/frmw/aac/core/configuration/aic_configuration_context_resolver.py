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

from .aic_configuration_scope_resolver_registry import AIcConfigurationScopeResolverRegistry

class AIcConfigurationContextResolver:
    def __init__(self, resolvers: AIcConfigurationScopeResolverRegistry) -> None:
        self.resolvers = resolvers

    def resolve(self, profile: AIcConfigurationProfile, context: Mapping[str, object]) -> tuple[AIcResolvedConfigurationScope, ...]:
        result: list[AIcResolvedConfigurationScope] = []
        seen: set[tuple[str, str | None]] = set()
        for definition in profile.configuration_scopes:
            resolver = self.resolvers.get(definition.configuration_scope_resolver_id)
            scope = resolver.resolve(AIcConfigurationScopeResolutionRequest(
                definition.configuration_scope_type,
                definition.id,
                dict(context),
            ))
            if scope is None:
                if definition.mandatory:
                    raise AIxConfigurationConflictError(
                        f"mandatory configuration-scope {definition.id!r} ({definition.configuration_scope_type}) could not be resolved"
                    )
                continue
            key = (scope.type, scope.id)
            if key in seen:
                raise AIxConfigurationConflictError(f"configuration-scope {scope.key!r} occurs more than once in the active chain")
            seen.add(key)
            ordered_bindings = tuple(sorted(
                definition.configuration_providers,
                key=lambda item: (-item.priority, item.configuration_provider_id),
            ))
            result.append(AIcResolvedConfigurationScope(definition.id, scope, ordered_bindings, definition.policy_authority))
        return tuple(result)
