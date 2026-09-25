from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcConfigurationProviderRegistration:
    id: str
    type: str
    settings: Mapping[str, object] = field(default_factory=dict)
    authentication_profile_id: str | None = None
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.type:
            raise ValueError("configuration-provider registration id and type must not be empty")
