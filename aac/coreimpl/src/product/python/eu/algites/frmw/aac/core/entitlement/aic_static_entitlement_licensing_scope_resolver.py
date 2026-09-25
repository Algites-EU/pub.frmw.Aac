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

class AIcStaticEntitlementLicensingScopeResolver(AIiEntitlementLicensingScopeResolver):
    def resolve(self, request: AIcEntitlementLicensingScopeResolutionRequest) -> AIcEntitlementLicensingScope | None:
        raw = request.context.get(request.licensing_scope_type)
        if raw is None:
            return None
        if isinstance(raw, AIcEntitlementSubject):
            return AIcEntitlementLicensingScope(request.licensing_scope_type, raw.id)
        if isinstance(raw, Mapping):
            raw_id = raw.get("id")
            if raw_id is None:
                return None
            return AIcEntitlementLicensingScope(request.licensing_scope_type, str(raw_id))
        return AIcEntitlementLicensingScope(request.licensing_scope_type, str(raw))

    def resolve_subject(self, request: AIcEntitlementLicensingScopeResolutionRequest) -> AIcEntitlementSubject | None:
        raw = request.context.get(request.licensing_scope_type)
        if raw is None:
            return None
        if isinstance(raw, AIcEntitlementSubject):
            return raw
        if isinstance(raw, Mapping):
            raw_id = raw.get("id")
            if raw_id is None:
                return None
            return AIcEntitlementSubject(
                str(raw_id),
                str(raw.get("display_name")) if raw.get("display_name") is not None else None,
                dict(raw.get("attributes", {})) if isinstance(raw.get("attributes", {}), Mapping) else {},
            )
        return AIcEntitlementSubject(str(raw))
