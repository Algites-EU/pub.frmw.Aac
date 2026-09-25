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

class AIiEntitlementRemediator(ABC):
    @abstractmethod
    def remediate(self, request: AIcEntitlementRemediationRequest) -> AIcEntitlementRemediationOutcome:
        """Attempt to obtain/refresh entitlement evidence for one denied permission."""
