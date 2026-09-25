from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from eu.algites.frmw.aac.core.presentation.api import (
    AIcDisplayContent,
    AIcDisplayText,
    normalize_display_content,
    normalize_display_text,
)

from .aic_ui_upgrade_diagnostic import AIcUiUpgradeDiagnostic
from .aic_ui_upgrade_replacement import AIcUiUpgradeReplacement

@dataclass(frozen=True, slots=True)
class AIcUiUpgradePlan:
    application_scope_id: str
    replacements: tuple[AIcUiUpgradeReplacement, ...]
    compatible: bool
    diagnostics: tuple[AIcUiUpgradeDiagnostic, ...] = ()
