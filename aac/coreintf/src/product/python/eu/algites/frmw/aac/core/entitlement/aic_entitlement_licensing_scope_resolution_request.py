from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcEntitlementLicensingScopeResolutionRequest:
    licensing_scope_type: str
    definition_id: str
    context: Mapping[str, object] = field(default_factory=dict)
