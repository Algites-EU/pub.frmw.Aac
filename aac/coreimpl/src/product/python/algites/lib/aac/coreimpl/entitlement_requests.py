from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from algites.lib.aac.coreintf.entitlement import AIcEntitlementLicensingScope
from algites.lib.aac.coreintf.entitlement import (
    AIcEntitlementDocument,
    AIcEntitlementIssuingRequest,
    AIcEntitlementSubject,
    AIcRequestedComponentGrant,
)

from .entitlement_documents import entitlement_request_digest
from .errors import AIxEntitlementError


class AIcEntitlementIssuingRequestService:
    """Generate and track request identities used to correlate returned entitlements.

    This is deliberately not an anti-cloning DRM mechanism. The request id/digest binds a
    returned entitlement to an exact request; issuer signature/trust still establishes that
    the granted rights were issued by an authorized vendor.
    """

    def __init__(self) -> None:
        self._requests: dict[str, AIcEntitlementIssuingRequest] = {}

    def create(
        self,
        licensing_scope: AIcEntitlementLicensingScope,
        subject: AIcEntitlementSubject,
        components: tuple[AIcRequestedComponentGrant, ...],
        *,
        request_id: str | None = None,
        generated_at: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AIcEntitlementIssuingRequest:
        if licensing_scope.id != subject.id:
            raise AIxEntitlementError("issuing request scope id must match subject id")
        request = AIcEntitlementIssuingRequest(
            format_version=1,
            request_id=request_id or str(uuid4()),
            requested_licensing_scope=licensing_scope,
            subject=subject,
            components=components,
            generated_at=generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            metadata=dict(metadata or {}),
        )
        request = replace(request, request_digest=entitlement_request_digest(request))
        self._requests[request.request_id] = request
        return request

    def put(self, request: AIcEntitlementIssuingRequest) -> AIcEntitlementIssuingRequest:
        expected = entitlement_request_digest(request)
        if request.request_digest is not None and request.request_digest != expected:
            raise AIxEntitlementError("issuing request digest does not match request content")
        normalized = request if request.request_digest == expected else replace(request, request_digest=expected)
        self._requests[normalized.request_id] = normalized
        return normalized

    def get(self, request_id: str) -> AIcEntitlementIssuingRequest:
        return self._requests[request_id]

    def validate_returned_entitlement(self, document: AIcEntitlementDocument) -> None:
        ref = document.issued_for_request
        if ref is None:
            return
        request = self._requests.get(ref.request_id)
        if request is None:
            raise AIxEntitlementError(f"entitlement references unknown issuing request {ref.request_id!r}")
        if request.request_digest != ref.request_digest:
            raise AIxEntitlementError("entitlement request digest does not match the recorded issuing request")
        if document.licensing_scope != request.requested_licensing_scope:
            raise AIxEntitlementError("entitlement licensing scope differs from its issuing request")
        if document.subject.id != request.subject.id:
            raise AIxEntitlementError("entitlement subject differs from its issuing request")
