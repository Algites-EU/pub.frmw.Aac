from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

@dataclass(frozen=True, slots=True)
class AIcPackageSelection:
    application_scope_id: str
    component_id: str
    component_version: int
    sha256: str
    selected_at: str
    previous_sha256: str | None = None
    previous_version: int | None = None
