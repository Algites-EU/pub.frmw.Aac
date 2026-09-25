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

class AIcEntitlementEvidenceVerifierRegistry:
    def __init__(self) -> None:
        self._verifiers: dict[str, AIiEntitlementEvidenceVerifier] = {}

    def register(self, evidence_type: str, verifier: AIiEntitlementEvidenceVerifier) -> None:
        if not evidence_type:
            raise ValueError("evidence_type must not be empty")
        self._verifiers[evidence_type] = verifier

    def verify(self, evidence: AIcEntitlementEvidence) -> AIcEntitlementEvidenceVerification:
        verifier = self._verifiers.get(evidence.evidence_type)
        if verifier is None:
            return AIcEntitlementEvidenceVerification(False, "", (f"no verifier registered for entitlement evidence type {evidence.evidence_type!r}",))
        return verifier.verify(evidence)
