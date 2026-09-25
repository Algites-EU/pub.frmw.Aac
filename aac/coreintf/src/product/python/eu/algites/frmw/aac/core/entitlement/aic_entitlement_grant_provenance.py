from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_entitlement_licensing_scope import AIcEntitlementLicensingScope

@dataclass(frozen=True, slots=True)
class AIcEntitlementGrantProvenance:
    entitlement_provider_id: str
    entitlement_id: str
    issuer_id: str
    licensing_scope: AIcEntitlementLicensingScope
    capability_id: str
    capability_version: int
    permission_id: str
    valid_from: str | None = None
    valid_until: str | None = None
