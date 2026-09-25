from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from ..readiness.api import AInReadinessState

@dataclass(frozen=True, slots=True)
class AIcSolverExplanation:
    code: str
    message: str
    component_id: str | None = None
    caused_by_component_id: str | None = None
    capability_id: str | None = None
