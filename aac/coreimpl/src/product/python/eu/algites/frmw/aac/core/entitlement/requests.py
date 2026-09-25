from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4
from eu.algites.frmw.aac.core.entitlement.api import AIcEntitlementLicensingScope
from eu.algites.frmw.aac.core.entitlement.api import (
    AIcEntitlementDocument,
    AIcEntitlementIssuingRequest,
    AIcEntitlementSubject,
    AIcRequestedComponentGrant,
)
from eu.algites.frmw.aac.core.entitlement.documents import entitlement_request_digest
from eu.algites.frmw.aac.core.implementation.errors import AIxEntitlementError

from .aic_entitlement_issuing_request_service import AIcEntitlementIssuingRequestService
