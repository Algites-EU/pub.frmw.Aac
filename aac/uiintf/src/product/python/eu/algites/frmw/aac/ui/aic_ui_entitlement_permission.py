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

def _optional_display_text(value: AIcDisplayText | str | None) -> AIcDisplayText | None:
    if value == "":
        return None
    return normalize_display_text(value)

@dataclass(frozen=True, slots=True)
class AIcUiEntitlementPermission:
    component_id: str
    capability_id: str
    capability_version: int
    permission_id: str
    effective_from: str | None = None
    effective_until: str | None = None
    licensing_scope: str | None = None
    entitlement_id: str | None = None
    issuer_id: str | None = None
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    implicit: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _optional_display_text(self.name))
        object.__setattr__(self, "description", _optional_display_text(self.description))
