from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..readiness import AInReadinessState


class AInTargetStateRequestMode(str, Enum):
    EXACT = "EXACT"
    ONE_OF = "ONE_OF"
    LATEST_COMPATIBLE = "LATEST_COMPATIBLE"


class AInTargetStateChangeDirection(str, Enum):
    INSTALL = "INSTALL"
    UPGRADE = "UPGRADE"
    DOWNGRADE = "DOWNGRADE"
    UNCHANGED = "UNCHANGED"


@dataclass(frozen=True, slots=True)
class AIcTargetStateRequest:
    component_id: str
    mode: AInTargetStateRequestMode = AInTargetStateRequestMode.LATEST_COMPATIBLE
    versions: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("target-state request component_id must not be empty")
        if any(version < 1 for version in self.versions):
            raise ValueError("target-state request versions must be >= 1")
        if self.mode is AInTargetStateRequestMode.EXACT and len(self.versions) != 1:
            raise ValueError("EXACT target-state request requires exactly one version")
        if self.mode is AInTargetStateRequestMode.ONE_OF and not self.versions:
            raise ValueError("ONE_OF target-state request requires at least one version")
        if self.mode is AInTargetStateRequestMode.LATEST_COMPATIBLE and self.versions:
            raise ValueError("LATEST_COMPATIBLE target-state request must not declare versions")

    @classmethod
    def exact(cls, component_id: str, version: int) -> "AIcTargetStateRequest":
        return cls(component_id, AInTargetStateRequestMode.EXACT, (version,))

    @classmethod
    def latest(cls, component_id: str) -> "AIcTargetStateRequest":
        return cls(component_id, AInTargetStateRequestMode.LATEST_COMPATIBLE, ())


@dataclass(frozen=True, slots=True)
class AIcSolverExplanation:
    code: str
    message: str
    component_id: str | None = None
    caused_by_component_id: str | None = None
    capability_id: str | None = None


@dataclass(frozen=True, slots=True)
class AIcSolverEntitlementDiagnostic:
    component_id: str
    capability_id: str
    capability_version: int
    permission_id: str
    possible_licensing_scopes: tuple[str, ...] = ()
    granted: bool = False
    entitlement_info_url: str | None = None


@dataclass(frozen=True, slots=True)
class AIcSolverReadinessDiagnostic:
    component_id: str
    state: AInReadinessState
    message: str


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


@dataclass(frozen=True, slots=True)
class AIcTargetStateSolverResult:
    requests: tuple[AIcTargetStateRequest, ...]
    primary: AIcTargetStateSolution | None
    alternatives: tuple[AIcTargetStateSolution, ...] = ()
    diagnostics: tuple[AIcSolverExplanation, ...] = ()
