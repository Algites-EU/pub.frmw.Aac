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

class AIcStaticEntitlementProvider(AIiEntitlementProvider):
    """In-memory evidence provider for tests/trusted bootstrap configuration."""

    def __init__(self, evidence: Mapping[str, Iterable[AIcEntitlementEvidence | AIcEntitlementDocument]]) -> None:
        normalized: dict[str, tuple[AIcEntitlementEvidence, ...]] = {}
        for key, values in evidence.items():
            items = []
            for value in values:
                if isinstance(value, AIcEntitlementEvidence):
                    items.append(value)
                else:
                    items.append(AIcEntitlementEvidence(value, "TRUSTED_BOOTSTRAP"))
            normalized[str(key)] = tuple(items)
        self._evidence = normalized

    def evidence(self, request: AIcEntitlementProviderRequest) -> tuple[AIcEntitlementEvidence, ...]:
        return self._evidence.get(request.licensing_scope.key, ())
