from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcRequestedCapabilityGrant:
    capability_id: str
    capability_version: int
    permissions: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.capability_id or self.capability_version < 1:
            raise ValueError("requested capability grant requires capability id/version")
        if len(self.permissions) != len(set(self.permissions)):
            raise ValueError("requested permission ids must be unique")
