from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcCapabilityRef:
    id: str
    version: int

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("capability id must not be empty")
        if self.version < 1:
            raise ValueError("capability version must be >= 1")
