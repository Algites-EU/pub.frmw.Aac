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

from .aic_ui_entitlement_permission import AIcUiEntitlementPermission

@dataclass(frozen=True, slots=True)
class AIcUiEntitlementStatus:
    component_id: str
    permissions: tuple[AIcUiEntitlementPermission, ...]
    next_transition_at: str | None = None
    diagnostics: tuple[str, ...] = ()
