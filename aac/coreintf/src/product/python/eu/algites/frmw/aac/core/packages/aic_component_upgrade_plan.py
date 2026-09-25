from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

from .aic_component_upgrade_replacement import AIcComponentUpgradeReplacement
from .aic_upgrade_compatibility_diagnostic import AIcUpgradeCompatibilityDiagnostic

@dataclass(frozen=True, slots=True)
class AIcComponentUpgradePlan:
    application_scope_id: str
    replacements: tuple[AIcComponentUpgradeReplacement, ...]
    compatible: bool
    diagnostics: tuple[AIcUpgradeCompatibilityDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        ids = [item.component_id for item in self.replacements]
        if len(ids) != len(set(ids)):
            raise ValueError("upgrade replacements must be unique by component_id")
        if self.compatible and any(item.blocking for item in self.diagnostics):
            raise ValueError("compatible upgrade plan must not contain blocking compatibility diagnostics")
