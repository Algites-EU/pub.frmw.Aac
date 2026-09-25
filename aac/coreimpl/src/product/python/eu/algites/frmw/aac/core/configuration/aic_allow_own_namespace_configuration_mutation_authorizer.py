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

class AIcAllowOwnNamespaceConfigurationMutationAuthorizer(AIiConfigurationMutationAuthorizer):
    """Baseline Core authorizer: caller may mutate only its own component namespace.

    Product profiles can replace this with principal/role-aware authorization.  The actor
    component id is supplied as ``actor_context['component_id']``; product/UI administrative
    principals may set ``configuration_admin=True``.
    """

    def authorized_capabilities(self, request, actor_context, provider_capabilities):
        technical = tuple(provider_capabilities)
        if actor_context.get("configuration_admin") is True or actor_context.get("component_id") == request.configuration_target.component_id:
            return technical
        return tuple(item for item in technical if item is AInConfigurationProviderCapability.READ)

    def authorize(self, change_set: AIcConfigurationChangeSet) -> tuple[bool, tuple[str, ...]]:
        actor = change_set.actor_context.get("component_id")
        if change_set.actor_context.get("configuration_admin") is True:
            return True, ()
        if actor == change_set.configuration_target.component_id:
            return True, ()
        return False, ("configuration mutation is outside the caller component namespace",)
