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

class AIcStaticConfigurationScopeResolver(AIiConfigurationScopeResolver):
    """Simple bootstrap/test resolver using a type->id mapping from the request context.

    SYSTEM commonly resolves without an id. Other configuration-scope types are present
    only when the supplied context contains an identity for that type.
    """

    def resolve(self, request: AIcConfigurationScopeResolutionRequest) -> AIcConfigurationScope | None:
        if request.configuration_scope_type == "SYSTEM":
            raw = request.context.get("SYSTEM")
            return AIcConfigurationScope("SYSTEM", str(raw) if raw is not None else None)
        raw = request.context.get(request.configuration_scope_type)
        if raw is None:
            return None
        return AIcConfigurationScope(request.configuration_scope_type, str(raw))
