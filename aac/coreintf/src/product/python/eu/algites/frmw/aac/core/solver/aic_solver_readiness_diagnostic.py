from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from ..readiness.api import AInReadinessState

@dataclass(frozen=True, slots=True)
class AIcSolverReadinessDiagnostic:
    component_id: str
    state: AInReadinessState
    message: str
