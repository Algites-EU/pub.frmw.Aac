from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AInReadinessState(str, Enum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    NOT_READY = "NOT_READY"


class AInReadinessRequirementSource(str, Enum):
    COMPONENT_CONFIGURATION = "COMPONENT_CONFIGURATION"
    PROVIDER_CONFIGURATION = "PROVIDER_CONFIGURATION"
    CONTEXT = "CONTEXT"


@dataclass(frozen=True, slots=True)
class AIcReadinessRequirementDescriptor:
    id: str
    source: AInReadinessRequirementSource
    key: str
    missing_state: AInReadinessState = AInReadinessState.NOT_READY
    message: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.key:
            raise ValueError("readiness requirement id/key must not be empty")
        if self.missing_state is AInReadinessState.READY:
            raise ValueError("missing readiness requirement cannot declare READY")


@dataclass(frozen=True, slots=True)
class AIcReadinessReason:
    code: str
    message: str
    state: AInReadinessState
    requirement_id: str | None = None
    key: str | None = None

    def __post_init__(self) -> None:
        if not self.code or not self.message:
            raise ValueError("readiness reason code/message must not be empty")
        if self.state is AInReadinessState.READY:
            raise ValueError("READY does not require a readiness reason")


@dataclass(frozen=True, slots=True)
class AIcReadinessResult:
    state: AInReadinessState = AInReadinessState.READY
    reasons: tuple[AIcReadinessReason, ...] = ()

    def __post_init__(self) -> None:
        if self.state is AInReadinessState.READY and self.reasons:
            raise ValueError("READY readiness result must not contain reasons")
        if self.state is not AInReadinessState.READY and not self.reasons:
            raise ValueError("non-READY readiness result requires at least one reason")


@dataclass(frozen=True, slots=True)
class AIcProviderReadiness:
    application_scope_id: str
    component_id: str
    provider_instance_id: str
    capability_ids: tuple[str, ...]
    state: AInReadinessState
    reasons: tuple[AIcReadinessReason, ...] = ()


@dataclass(frozen=True, slots=True)
class AIcCapabilityReadiness:
    application_scope_id: str
    capability_id: str
    state: AInReadinessState
    provider_instance_ids: tuple[str, ...] = ()
    reasons: tuple[AIcReadinessReason, ...] = ()


@dataclass(frozen=True, slots=True)
class AIcComponentReadiness:
    application_scope_id: str
    component_id: str
    state: AInReadinessState
    provider_instance_ids: tuple[str, ...] = ()
    reasons: tuple[AIcReadinessReason, ...] = ()
