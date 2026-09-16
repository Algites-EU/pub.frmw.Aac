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


class AIiEntitlementLicensingScopeResolver(ABC):
    @abstractmethod
    def resolve(self, request: AIcEntitlementLicensingScopeResolutionRequest) -> AIcEntitlementLicensingScope | None:
        """Resolve one entitlement-profile definition to a trusted concrete scope identity."""

    def resolve_subject(self, request: AIcEntitlementLicensingScopeResolutionRequest) -> AIcEntitlementSubject | None:
        """Resolve trusted subject metadata; default uses the resolved scope id only."""
        scope = self.resolve(request)
        if scope is None or scope.id is None:
            return None
        return AIcEntitlementSubject(scope.id)


class AIiEntitlementEvidenceVerifier(ABC):
    @abstractmethod
    def verify(self, evidence: AIcEntitlementEvidence) -> AIcEntitlementEvidenceVerification:
        """Verify entitlement evidence without interpreting component-owned permission semantics."""


class AIiEntitlementRemediator(ABC):
    @abstractmethod
    def remediate(self, request: AIcEntitlementRemediationRequest) -> AIcEntitlementRemediationOutcome:
        """Attempt to obtain/refresh entitlement evidence for one denied permission."""
