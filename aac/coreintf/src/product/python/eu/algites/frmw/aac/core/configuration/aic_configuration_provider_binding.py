from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcConfigurationProviderBinding:
    configuration_provider_id: str
    priority: int = 0

    def __post_init__(self) -> None:
        if not self.configuration_provider_id:
            raise ValueError("configuration_provider_id must not be empty")
