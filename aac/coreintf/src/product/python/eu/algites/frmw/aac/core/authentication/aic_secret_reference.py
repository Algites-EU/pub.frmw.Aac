from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcSecretReference:
    secret_provider_id: str
    key: str
    version: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.secret_provider_id:
            raise ValueError("secret_provider_id must not be empty")
        if not self.key:
            raise ValueError("secret reference key must not be empty")
