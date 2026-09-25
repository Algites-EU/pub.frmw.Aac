from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AIcProvidedCapability

from .ain_provider_access_mode import AInProviderAccessMode
from .ain_provider_instance_state import AInProviderInstanceState

@dataclass(frozen=True, slots=True)
class AIcProviderInstance:
    id: str
    component_id: str
    provider_definition_id: str
    name: str
    capabilities: tuple[AIcProvidedCapability, ...]
    implementation_class: str
    access_mode: AInProviderAccessMode = AInProviderAccessMode.READ_WRITE
    configuration: Mapping[str, object] = field(default_factory=dict)
    configuration_schema: str | None = None
    state: AInProviderInstanceState = AInProviderInstanceState.CONFIGURED

    def __post_init__(self) -> None:
        if not self.id or not self.component_id or not self.provider_definition_id or not self.name:
            raise ValueError("provider instance identity fields must not be empty")
        if not self.capabilities:
            raise ValueError("provider instance must provide at least one capability")
        ids = [capability.id for capability in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError("provider instance capability ids must be unique")

    def capability(self, capability_id: str) -> AIcProvidedCapability:
        for capability in self.capabilities:
            if capability.id == capability_id:
                return capability
        raise KeyError(capability_id)

    def supports_capability(self, capability_id: str) -> bool:
        return any(capability.id == capability_id for capability in self.capabilities)
