from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_entitlement_licensing_scope import AIcEntitlementLicensingScope
from .aic_entitlement_provider_binding import AIcEntitlementProviderBinding
from .aic_entitlement_subject import AIcEntitlementSubject

@dataclass(frozen=True, slots=True)
class AIcResolvedEntitlementLicensingScope:
    definition_id: str
    licensing_scope: AIcEntitlementLicensingScope
    entitlement_providers: tuple[AIcEntitlementProviderBinding, ...] = ()
    subject: AIcEntitlementSubject | None = None
