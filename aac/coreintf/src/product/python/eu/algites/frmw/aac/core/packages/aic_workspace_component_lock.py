from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

from .aic_workspace_component_lock_entry import AIcWorkspaceComponentLockEntry

@dataclass(frozen=True, slots=True)
class AIcWorkspaceComponentLock:
    workspace_id: str
    entries: tuple[AIcWorkspaceComponentLockEntry, ...]

    def __post_init__(self) -> None:
        if not self.workspace_id:
            raise ValueError("workspace component lock workspace_id must not be empty")
        ids = [item.component_id for item in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("workspace component lock entries must be unique by component_id")

    def entry(self, component_id: str) -> AIcWorkspaceComponentLockEntry | None:
        return next((item for item in self.entries if item.component_id == component_id), None)
