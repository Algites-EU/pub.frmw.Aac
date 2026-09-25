from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_policy import AIcConfigurationPolicy

@dataclass(frozen=True, slots=True)
class AIcConfigurationContribution:
    property_id: str
    value: object | None = None
    has_value: bool = False
    policy_modes: tuple[AIcConfigurationPolicy, ...] = ()
    configuration_schema_id: str | None = None
    configuration_schema_version: int | None = None
    written_by_component_version: int | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.property_id:
            raise ValueError("configuration contribution property_id must not be empty")
        if not self.has_value and self.value is not None:
            raise ValueError("value requires has_value=True so explicit null remains representable")
        if self.configuration_schema_version is not None and self.configuration_schema_version < 1:
            raise ValueError("configuration_schema_version must be >= 1")
        if self.written_by_component_version is not None and self.written_by_component_version < 1:
            raise ValueError("written_by_component_version must be >= 1")
