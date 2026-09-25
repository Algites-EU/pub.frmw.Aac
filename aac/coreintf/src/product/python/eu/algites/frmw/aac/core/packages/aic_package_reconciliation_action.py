from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

from .aic_package_candidate import AIcPackageCandidate

@dataclass(frozen=True, slots=True)
class AIcPackageReconciliationAction:
    component_id: str
    action: str
    candidate: AIcPackageCandidate | None = None
    reason: str | None = None
