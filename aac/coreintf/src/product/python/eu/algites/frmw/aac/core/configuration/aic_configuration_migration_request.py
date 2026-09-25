from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

from .aic_configuration_persisted_payload import AIcConfigurationPersistedPayload

@dataclass(frozen=True, slots=True)
class AIcConfigurationMigrationRequest:
    source: AIcConfigurationPersistedPayload
    target_configuration_schema_version: int

    def __post_init__(self) -> None:
        if self.target_configuration_schema_version < 1:
            raise ValueError("target configuration schema version must be >= 1")
