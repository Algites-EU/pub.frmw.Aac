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

from .aic_configuration_provider_registry import AIcConfigurationProviderRegistry

class AIcConfigurationMutationService:
    def __init__(self, providers: AIcConfigurationProviderRegistry, authorizer: AIiConfigurationMutationAuthorizer) -> None:
        self.providers = providers
        self.authorizer = authorizer

    def access(self, request: AIcConfigurationProviderRequest, actor_context: Mapping[str, object] | None = None) -> AIcConfigurationProviderAccess:
        provider = self.providers.get(request.context.get("configuration_provider_id", "")) if request.context.get("configuration_provider_id") else None
        if provider is None:
            raise ValueError("configuration provider id must be supplied in request.context['configuration_provider_id']")
        technical = tuple(provider.capabilities(request))
        authorized = tuple(self.authorizer.authorized_capabilities(request, dict(actor_context or {}), technical))
        diagnostics = () if set(authorized) == set(technical) else ("one or more provider mutation capabilities are not authorized for the current principal",)
        return AIcConfigurationProviderAccess(
            request.configuration_scope, str(request.context["configuration_provider_id"]), request.configuration_target, technical, authorized, diagnostics
        )

    def access_for(
        self, configuration_provider_id: str, request: AIcConfigurationProviderRequest, actor_context: Mapping[str, object] | None = None
    ) -> AIcConfigurationProviderAccess:
        provider = self.providers.get(configuration_provider_id)
        technical = tuple(provider.capabilities(request))
        authorized = tuple(self.authorizer.authorized_capabilities(request, dict(actor_context or {}), technical))
        diagnostics = () if set(authorized) == set(technical) else ("one or more provider mutation capabilities are not authorized for the current principal",)
        return AIcConfigurationProviderAccess(
            request.configuration_scope, configuration_provider_id, request.configuration_target, technical, authorized, diagnostics
        )

    def apply(self, change_set: AIcConfigurationChangeSet) -> AIcConfigurationMutationResult:
        provider = self.providers.get(change_set.configuration_provider_id)
        request = AIcConfigurationProviderRequest(
            change_set.configuration_target, change_set.configuration_scope, change_set.actor_context
        )
        capabilities = set(provider.capabilities(request))
        required = {AInConfigurationProviderCapability.READ}
        for change in change_set.changes:
            if change.operation.value == "SET_VALUE":
                required.add(AInConfigurationProviderCapability.WRITE_VALUE)
            elif change.operation.value == "DELETE_VALUE":
                required.add(AInConfigurationProviderCapability.DELETE_VALUE)
            elif change.operation.value == "SET_POLICY":
                required.add(AInConfigurationProviderCapability.WRITE_POLICY)
            elif change.operation.value == "DELETE_POLICY":
                required.add(AInConfigurationProviderCapability.DELETE_POLICY)
        missing = required - capabilities
        if missing:
            raise AIxConfigurationPolicyError(
                "configuration-provider lacks required mutation capabilities: "
                + ", ".join(sorted(item.value for item in missing))
            )
        authorized = set(self.authorizer.authorized_capabilities(request, change_set.actor_context, tuple(capabilities)))
        unauthorized = required - authorized
        if unauthorized:
            raise AIxConfigurationPolicyError(
                "configuration mutation capability is not authorized: " + ", ".join(sorted(item.value for item in unauthorized))
            )
        allowed, diagnostics = self.authorizer.authorize(change_set)
        if not allowed:
            raise AIxConfigurationPolicyError("configuration mutation is not authorized: " + "; ".join(diagnostics))
        if len(change_set.changes) > 1 and AInConfigurationProviderCapability.ATOMIC_CHANGE_SET not in capabilities:
            raise AIxConfigurationPolicyError("configuration-provider does not support atomic multi-change mutation")
        return provider.apply_changes(change_set)
