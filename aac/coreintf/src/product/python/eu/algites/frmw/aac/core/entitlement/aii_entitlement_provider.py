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

class AIiEntitlementProvider(ABC):
    @abstractmethod
    def evidence(self, request: AIcEntitlementProviderRequest) -> tuple[AIcEntitlementEvidence, ...]:
        """Return entitlement evidence applicable to one concrete entitlement licensing-scope subject."""
