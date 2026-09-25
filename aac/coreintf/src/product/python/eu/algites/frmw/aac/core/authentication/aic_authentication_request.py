from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

from .aic_authentication_profile import AIcAuthenticationProfile

@dataclass(frozen=True, slots=True)
class AIcAuthenticationRequest:
    profile: AIcAuthenticationProfile
    transport_kind: str
    endpoint: str | None = None
    context: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.transport_kind:
            raise ValueError("transport_kind must not be empty")
