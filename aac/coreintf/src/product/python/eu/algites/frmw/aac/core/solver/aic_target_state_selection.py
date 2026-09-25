from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from ..readiness.api import AInReadinessState

from .ain_target_state_change_direction import AInTargetStateChangeDirection

@dataclass(frozen=True, slots=True)
class AIcTargetStateSelection:
    component_id: str
    current_version: int | None
    target_version: int
    direction: AInTargetStateChangeDirection
    requested: bool = False
    source_id: str | None = None
    artifact_id: str | None = None
    target_sha256: str | None = None
    download_required: bool = False
    install_required: bool = False
