from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..context.api import AIcConfigurationScope
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcConfigurationProfileSourceRegistration:
    id: str
    uri: str
    authentication_profile_id: str | None = None
    required: bool = True
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.uri:
            raise ValueError("configuration-profile source id/uri must not be empty")
