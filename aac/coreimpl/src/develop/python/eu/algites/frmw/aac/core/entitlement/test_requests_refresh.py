from dataclasses import replace
from datetime import datetime, timezone

from eu.algites.frmw.aac.core.entitlement.api import AIcEntitlementLicensingScope
from eu.algites.frmw.aac.core.entitlement.api import (
    AIcEntitlementComponentGrant, AIcEntitlementDocument, AIcEntitlementIssuer,
    AIcEntitlementRequestReference, AIcEntitlementSubject, AIcRequestedComponentGrant,
)
from eu.algites.frmw.aac.core.entitlement.refresh import AIcEntitlementRefreshPlanner
from eu.algites.frmw.aac.core.entitlement.requests import AIcEntitlementIssuingRequestService
from eu.algites.frmw.aac.core.entitlement.api import AIcEntitlementContext


def test_issuing_request_digest_binds_returned_entitlement():
    service = AIcEntitlementIssuingRequestService()
    request = service.create(
        AIcEntitlementLicensingScope("WORKSPACE", "ws-1"), AIcEntitlementSubject("ws-1"),
        (AIcRequestedComponentGrant("vendor.foo", ()),), request_id="req-1", generated_at="2026-09-14T00:00:00Z"
    )
    document = AIcEntitlementDocument(
        1, "ent-1", AIcEntitlementIssuer("vendor.example"), AIcEntitlementLicensingScope("WORKSPACE", "ws-1"),
        AIcEntitlementSubject("ws-1"), (AIcEntitlementComponentGrant("vendor.foo", ()),),
        issued_for_request=AIcEntitlementRequestReference(request.request_id, request.request_digest),
    )
    service.validate_returned_entitlement(document)

    bad = replace(document, issued_for_request=AIcEntitlementRequestReference(request.request_id, "sha256:bad"))
    try:
        service.validate_returned_entitlement(bad)
    except Exception as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("bad request digest must fail")


def test_refresh_planner_detects_due_transition():
    context = AIcEntitlementContext("vendor.foo", next_transition_at="2026-09-14T12:00:00Z")
    assert AIcEntitlementRefreshPlanner.due((context,), datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc))
    assert not AIcEntitlementRefreshPlanner.due((context,), datetime(2026, 9, 14, 11, 59, tzinfo=timezone.utc))
