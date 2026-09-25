from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

@dataclass(frozen=True, slots=True)
class AIcPackageTransactionRecovery:
    transaction_id: str
    phase: AInPersistenceTransactionPhase
    action: str
    diagnostics: tuple[str, ...] = ()
