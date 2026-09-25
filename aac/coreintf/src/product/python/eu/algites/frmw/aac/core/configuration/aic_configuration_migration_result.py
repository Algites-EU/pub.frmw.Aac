from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_policy import AIcConfigurationPolicy

@dataclass(frozen=True, slots=True)
class AIcConfigurationMigrationResult:
    configuration_schema_id: str
    configuration_schema_version: int
    values: Mapping[str, object]
    policies: Mapping[str, tuple[AIcConfigurationPolicy, ...]] = field(default_factory=dict)
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.configuration_schema_id or self.configuration_schema_version < 1:
            raise ValueError("configuration migration result requires schema id/version >= 1")
