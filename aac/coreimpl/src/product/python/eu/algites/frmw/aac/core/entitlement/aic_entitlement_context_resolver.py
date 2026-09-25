from __future__ import annotations
from datetime import datetime, timezone
from typing import Callable, Iterable, Mapping
from eu.algites.frmw.aac.core.entitlement.api import AIcEntitlementLicensingScope
from eu.algites.frmw.aac.core.descriptor.api import AIcComponentDescriptor
from eu.algites.frmw.aac.core.entitlement.api import (
    AIcCapabilityEntitlementContext,
    AIcEffectiveEntitlementPermission,
    AIcEntitlementContext,
    AIcEntitlementDocument,
    AIcEntitlementEvidence,
    AIcEntitlementEvidenceVerification,
    AIcEntitlementGrantProvenance,
    AIcEntitlementSubject,
    AIcEntitlementProfile,
    AIcEntitlementProviderRequest,
    AIcEntitlementLicensingScopeResolutionRequest,
    AIcResolvedEntitlementLicensingScope,
    AIiEntitlementEvidenceVerifier,
    AIiEntitlementProvider,
    AIiEntitlementLicensingScopeResolver,
)
from eu.algites.frmw.aac.core.instances.api import AIcProviderInstance
from eu.algites.frmw.aac.core.implementation.errors import AIxEntitlementError
from eu.algites.frmw.aac.core.entitlement.trust import AIcTrustedEntitlementIssuerRegistry

from .aic_entitlement_licensing_scope_resolver_registry import AIcEntitlementLicensingScopeResolverRegistry

class AIcEntitlementContextResolver:
    def __init__(self, resolvers: AIcEntitlementLicensingScopeResolverRegistry) -> None:
        self.resolvers = resolvers

    def resolve(self, profile: AIcEntitlementProfile, context: Mapping[str, object]) -> tuple[AIcResolvedEntitlementLicensingScope, ...]:
        result: list[AIcResolvedEntitlementLicensingScope] = []
        seen: set[tuple[str, str | None]] = set()
        for definition in profile.licensing_scopes:
            resolver = self.resolvers.get(definition.licensing_scope_resolver_id)
            resolution_request = AIcEntitlementLicensingScopeResolutionRequest(
                definition.licensing_scope_type, definition.id, dict(context)
            )
            scope = resolver.resolve(resolution_request)
            subject = resolver.resolve_subject(resolution_request)
            if scope is None:
                if definition.mandatory:
                    raise AIxEntitlementError(
                        f"mandatory entitlement licensing-scope {definition.id!r} ({definition.licensing_scope_type}) could not be resolved"
                    )
                continue
            if subject is not None and scope.id != subject.id:
                raise AIxEntitlementError(
                    f"entitlement licensing-scope resolver {definition.licensing_scope_resolver_id!r} returned inconsistent scope/subject ids"
                )
            key = (scope.type, scope.id)
            if key in seen:
                raise AIxEntitlementError(f"entitlement licensing-scope {scope.key!r} occurs more than once in the active entitlement profile")
            seen.add(key)
            result.append(AIcResolvedEntitlementLicensingScope(definition.id, scope, definition.entitlement_providers, subject))
        return tuple(result)
