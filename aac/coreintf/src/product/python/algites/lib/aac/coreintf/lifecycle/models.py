from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class AInLifecycleStage(str, Enum):
    DISCOVER = "DISCOVER"
    VERIFY = "VERIFY"
    ADMIT_CONTRACTS = "ADMIT_CONTRACTS"
    PROVISION = "PROVISION"
    VALIDATE = "VALIDATE"
    EVALUATE_ENTITLEMENT = "EVALUATE_ENTITLEMENT"
    RESOLVE = "RESOLVE"
    INSTANTIATE = "INSTANTIATE"
    WIRE = "WIRE"
    ACTIVATABLE = "ACTIVATABLE"
    ACTIVATE = "ACTIVATE"
    SUSPEND = "SUSPEND"
    DEACTIVATE = "DEACTIVATE"
    UNPROVISION = "UNPROVISION"


class AInLifecycleState(str, Enum):
    INSTALLED = "INSTALLED"
    VERIFIED = "VERIFIED"
    PROVISIONED_UNCONFIGURED = "PROVISIONED_UNCONFIGURED"
    PROVISIONED = "PROVISIONED"
    RESOLVED = "RESOLVED"
    INSTANTIATED = "INSTANTIATED"
    WIRED = "WIRED"
    ACTIVATABLE = "ACTIVATABLE"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    FAILED = "FAILED"
    DEACTIVATED = "DEACTIVATED"


@dataclass(frozen=True, slots=True)
class AIcLifecycleContext:
    application_scope_id: str
    component_id: str
    component_version: int
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AIcValidationResult:
    valid: bool
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AIcLifecycleStatus:
    state: AInLifecycleState
    completed_stages: tuple[AInLifecycleStage, ...] = ()
    last_failure_stage: AInLifecycleStage | None = None
    diagnostics: tuple[str, ...] = ()
