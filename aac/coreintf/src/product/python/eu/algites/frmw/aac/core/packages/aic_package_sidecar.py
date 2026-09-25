from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

@dataclass(frozen=True, slots=True)
class AIcPackageSidecar:
    uri: str
    suffix: str
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.uri or not self.suffix or not self.suffix.startswith("."):
            raise ValueError("package sidecar requires uri and dot-prefixed suffix")
