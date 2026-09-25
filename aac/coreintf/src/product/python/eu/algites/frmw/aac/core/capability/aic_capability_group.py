from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcCapabilityGroup:
    id: str
    parent_group_id: str | None = None
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("capability group id must not be empty")
        if self.parent_group_id is not None and not self.parent_group_id:
            raise ValueError("parent capability group id must not be empty")
        if self.parent_group_id == self.id:
            raise ValueError("capability group cannot be its own parent")
        if self.name is None:
            raise ValueError("capability group requires display name")
