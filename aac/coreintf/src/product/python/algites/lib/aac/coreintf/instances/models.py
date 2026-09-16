from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class AInProviderInstanceState(str, Enum):
    UNCONFIGURED = "UNCONFIGURED"
    CONFIGURED = "CONFIGURED"
    ACTIVATABLE = "ACTIVATABLE"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class AIcProviderInstance:
    id: str
    component_id: str
    provider_definition_id: str
    name: str
    capability_id: str
    capability_versions: tuple[int, ...]
    implementation_class: str
    configuration: Mapping[str, object] = field(default_factory=dict)
    configuration_schema: str | None = None
    state: AInProviderInstanceState = AInProviderInstanceState.CONFIGURED

    @property
    def capability_version(self) -> int:
        return max(self.capability_versions)


@dataclass(frozen=True, slots=True)
class AIcBinding:
    consumer_instance_id: str
    requirement_id: str
    provider_instance_id: str
    capability_id: str
    capability_version: int


@dataclass(frozen=True, slots=True)
class AIcBindingPreference:
    """Core-owned topology preference; references stable instance IDs, never names."""

    consumer_instance_id: str
    requirement_id: str
    provider_instance_ids: tuple[str, ...]
