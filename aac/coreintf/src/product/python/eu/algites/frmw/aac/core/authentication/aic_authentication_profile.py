from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_authentication_parameter import AIcAuthenticationParameter

@dataclass(frozen=True, slots=True)
class AIcAuthenticationProfile:
    id: str
    mechanism: str
    parameters: Mapping[str, AIcAuthenticationParameter] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("authentication profile id must not be empty")
        mechanism = self.mechanism.strip()
        if not mechanism:
            raise ValueError("authentication mechanism must not be empty")
        object.__setattr__(self, "mechanism", mechanism)
