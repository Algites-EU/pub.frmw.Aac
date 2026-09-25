from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

from .aic_component_upgrade_replacement import AIcComponentUpgradeReplacement

@dataclass(frozen=True, slots=True)
class AIcComponentUpgradeTransactionOutcome:
    application_scope_id: str
    replacements: tuple[AIcComponentUpgradeReplacement, ...]
    rolled_back: bool = False
    diagnostics: tuple[str, ...] = ()
