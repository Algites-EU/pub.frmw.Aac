from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcSecretProviderRegistration:
    id: str
    type: str
    settings: Mapping[str, object] = field(default_factory=dict)
    bootstrap_safe: bool = False
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.type:
            raise ValueError("secret-provider registration id/type must not be empty")
