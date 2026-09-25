from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .ain_lifecycle_stage import AInLifecycleStage
from .ain_lifecycle_state import AInLifecycleState

@dataclass(frozen=True, slots=True)
class AIcLifecycleStatus:
    state: AInLifecycleState
    completed_stages: tuple[AInLifecycleStage, ...] = ()
    last_failure_stage: AInLifecycleStage | None = None
    diagnostics: tuple[str, ...] = ()
