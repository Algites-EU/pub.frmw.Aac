from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcSchemaRef:
    id: str
    version: int

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("schema id must not be empty")
        if self.version < 1:
            raise ValueError("schema version must be >= 1")
