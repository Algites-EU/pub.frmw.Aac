from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

@dataclass(frozen=True, slots=True)
class AIcWorkspaceComponentRequirement:
    component_id: str
    versions: tuple[int, ...] = ()
    required: bool = True
    source_ids: tuple[str, ...] = ()
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("workspace component requirement component_id must not be empty")
        if any(version < 1 for version in self.versions):
            raise ValueError("workspace component requirement versions must be >= 1")
        if len(self.versions) != len(set(self.versions)):
            raise ValueError("workspace component requirement versions must be unique")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("workspace component requirement source_ids must be unique")

    def accepts(self, version: int) -> bool:
        return not self.versions or version in self.versions
