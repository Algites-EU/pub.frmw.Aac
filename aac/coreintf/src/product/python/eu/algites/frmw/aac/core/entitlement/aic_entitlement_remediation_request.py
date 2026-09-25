from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcEntitlementRemediationRequest:
    component_id: str
    provider_instance_id: str | None
    capability_id: str
    capability_version: int
    permission_id: str | None
    remediation_hint: str | None = None
    context: Mapping[str, object] = field(default_factory=dict)
