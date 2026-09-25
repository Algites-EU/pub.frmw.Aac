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

@dataclass(frozen=True, slots=True)
class AIcUiUpgradeReplacement:
    component_id: str
    previous_version: int
    target_version: int
