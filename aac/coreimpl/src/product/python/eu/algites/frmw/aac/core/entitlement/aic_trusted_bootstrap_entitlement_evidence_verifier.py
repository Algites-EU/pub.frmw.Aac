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

class AIcTrustedBootstrapEntitlementEvidenceVerifier(AIiEntitlementEvidenceVerifier):
    """Reference verifier for evidence already authenticated by a trusted bootstrap provider.

    This is intentionally not a cryptographic file verifier. Signed-file/Sigstore evidence can
    register a different AIiEntitlementEvidenceVerifier without changing entitlement semantics.
    """

    def verify(self, evidence: AIcEntitlementEvidence) -> AIcEntitlementEvidenceVerification:
        return AIcEntitlementEvidenceVerification(True, "_AAC.trusted-bootstrap")
