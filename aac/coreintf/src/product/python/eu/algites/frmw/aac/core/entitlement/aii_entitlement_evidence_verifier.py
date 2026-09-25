from __future__ import annotations
from abc import ABC, abstractmethod
from .models import (
    AIcEntitlementEvidence,
    AIcEntitlementEvidenceVerification,
    AIcEntitlementProviderRequest,
    AIcEntitlementLicensingScopeResolutionRequest,
    AIcEntitlementRemediationRequest,
    AIcEntitlementRemediationOutcome,
    AIcEntitlementSubject,
)
from .models import AIcEntitlementLicensingScope

class AIiEntitlementEvidenceVerifier(ABC):
    @abstractmethod
    def verify(self, evidence: AIcEntitlementEvidence) -> AIcEntitlementEvidenceVerification:
        """Verify entitlement evidence without interpreting component-owned permission semantics."""
