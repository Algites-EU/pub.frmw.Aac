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

class AIcEntitlementLicensingScopeResolverRegistry:
    def __init__(self) -> None:
        self._resolvers: dict[str, AIiEntitlementLicensingScopeResolver] = {}

    def register(self, licensing_scope_resolver_id: str, resolver: AIiEntitlementLicensingScopeResolver) -> None:
        if not licensing_scope_resolver_id:
            raise ValueError("licensing_scope_resolver_id must not be empty")
        self._resolvers[licensing_scope_resolver_id] = resolver

    def get(self, licensing_scope_resolver_id: str) -> AIiEntitlementLicensingScopeResolver:
        return self._resolvers[licensing_scope_resolver_id]
