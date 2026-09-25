from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_policy import AIcConfigurationPolicy
from .aic_configuration_target import AIcConfigurationTarget

@dataclass(frozen=True, slots=True)
class AIcConfigurationPersistedPayload:
    configuration_target: AIcConfigurationTarget
    configuration_schema_id: str
    configuration_schema_version: int
    written_by_component_version: int
    values: Mapping[str, object] = field(default_factory=dict)
    policies: Mapping[str, tuple[AIcConfigurationPolicy, ...]] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.configuration_schema_id or self.configuration_schema_version < 1:
            raise ValueError("persisted configuration payload requires schema id/version >= 1")
        if self.written_by_component_version < 1:
            raise ValueError("written_by_component_version must be >= 1")
