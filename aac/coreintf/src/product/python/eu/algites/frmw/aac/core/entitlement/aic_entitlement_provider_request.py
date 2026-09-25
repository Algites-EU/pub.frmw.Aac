from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_entitlement_licensing_scope import AIcEntitlementLicensingScope
from .aic_entitlement_subject import AIcEntitlementSubject

@dataclass(frozen=True, slots=True)
class AIcEntitlementProviderRequest:
    licensing_scope: AIcEntitlementLicensingScope
    context: Mapping[str, object] = field(default_factory=dict)
    subject: AIcEntitlementSubject | None = None
