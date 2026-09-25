from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

from .aic_package_selection import AIcPackageSelection

@dataclass(frozen=True, slots=True)
class AIcPackageSelectionManifest:
    record_revision: int
    selections: tuple[AIcPackageSelection, ...] = ()
    last_transaction_id: str | None = None

    def __post_init__(self) -> None:
        if self.record_revision < 0:
            raise ValueError("package selection record_revision must not be negative")
        keys = [(item.application_scope_id, item.component_id) for item in self.selections]
        if len(keys) != len(set(keys)):
            raise ValueError("package selection manifest contains duplicate scope/component entries")
