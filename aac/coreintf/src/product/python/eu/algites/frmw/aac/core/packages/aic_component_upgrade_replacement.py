from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

@dataclass(frozen=True, slots=True)
class AIcComponentUpgradeReplacement:
    component_id: str
    previous_version: int
    target_version: int
    previous_sha256: str | None = None
    target_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.component_id or self.previous_version < 1 or self.target_version < 1:
            raise ValueError("component upgrade replacement requires component id and versions >= 1")
        if self.target_version == self.previous_version and self.target_sha256 == self.previous_sha256:
            raise ValueError("component upgrade replacement must change version and/or artifact digest")
