from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from .aic_readiness_reason import AIcReadinessReason
from .ain_readiness_state import AInReadinessState

@dataclass(frozen=True, slots=True)
class AIcProviderReadiness:
    application_scope_id: str
    component_id: str
    provider_instance_id: str
    capability_ids: tuple[str, ...]
    state: AInReadinessState
    reasons: tuple[AIcReadinessReason, ...] = ()
