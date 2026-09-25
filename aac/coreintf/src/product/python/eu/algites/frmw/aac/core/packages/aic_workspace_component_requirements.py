from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

from .aic_workspace_component_requirement import AIcWorkspaceComponentRequirement
from .ain_package_update_policy import AInPackageUpdatePolicy

@dataclass(frozen=True, slots=True)
class AIcWorkspaceComponentRequirements:
    workspace_id: str
    requirements: tuple[AIcWorkspaceComponentRequirement, ...]
    update_policy: AInPackageUpdatePolicy = AInPackageUpdatePolicy.MANUAL

    def __post_init__(self) -> None:
        if not self.workspace_id:
            raise ValueError("workspace_id must not be empty")
        ids = [item.component_id for item in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("workspace component requirements must be unique by component_id")
