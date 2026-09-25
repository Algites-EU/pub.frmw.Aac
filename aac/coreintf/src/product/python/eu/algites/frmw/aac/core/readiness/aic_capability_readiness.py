from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from .aic_readiness_reason import AIcReadinessReason
from .ain_readiness_state import AInReadinessState

@dataclass(frozen=True, slots=True)
class AIcCapabilityReadiness:
    application_scope_id: str
    capability_id: str
    state: AInReadinessState
    provider_instance_ids: tuple[str, ...] = ()
    reasons: tuple[AIcReadinessReason, ...] = ()
