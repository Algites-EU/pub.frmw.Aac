from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from ..readiness.api import AInReadinessState

from .aic_solver_explanation import AIcSolverExplanation
from .aic_target_state_request import AIcTargetStateRequest
from .aic_target_state_solution import AIcTargetStateSolution

@dataclass(frozen=True, slots=True)
class AIcTargetStateSolverResult:
    requests: tuple[AIcTargetStateRequest, ...]
    primary: AIcTargetStateSolution | None
    alternatives: tuple[AIcTargetStateSolution, ...] = ()
    diagnostics: tuple[AIcSolverExplanation, ...] = ()
