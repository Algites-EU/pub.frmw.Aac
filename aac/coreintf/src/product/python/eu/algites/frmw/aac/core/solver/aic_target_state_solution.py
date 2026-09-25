from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from ..readiness.api import AInReadinessState

from .aic_solver_entitlement_diagnostic import AIcSolverEntitlementDiagnostic
from .aic_solver_explanation import AIcSolverExplanation
from .aic_solver_readiness_diagnostic import AIcSolverReadinessDiagnostic
from .aic_target_state_selection import AIcTargetStateSelection
from .ain_target_state_change_direction import AInTargetStateChangeDirection

@dataclass(frozen=True, slots=True)
class AIcTargetStateSolution:
    selections: tuple[AIcTargetStateSelection, ...]
    explanations: tuple[AIcSolverExplanation, ...] = ()
    entitlement_diagnostics: tuple[AIcSolverEntitlementDiagnostic, ...] = ()
    readiness_diagnostics: tuple[AIcSolverReadinessDiagnostic, ...] = ()
    recommended: bool = True
    contains_downgrade: bool = False
    freshness_penalty: int = 0

    @property
    def changed(self) -> tuple[AIcTargetStateSelection, ...]:
        return tuple(item for item in self.selections if item.direction is not AInTargetStateChangeDirection.UNCHANGED)
