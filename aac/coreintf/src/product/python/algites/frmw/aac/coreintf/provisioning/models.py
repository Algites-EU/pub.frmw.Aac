from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from ..descriptor import AIcComponentDescriptor


@dataclass(frozen=True, slots=True)
class AIcProvisionContext:
    application_scope_id: str
    component: AIcComponentDescriptor
    existing_state: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AIcRequestedStateChange:
    key: str
    value: object


@dataclass(frozen=True, slots=True)
class AIcProvisioningResult:
    requested_changes: tuple[AIcRequestedStateChange, ...] = ()
    diagnostics: tuple[str, ...] = ()
