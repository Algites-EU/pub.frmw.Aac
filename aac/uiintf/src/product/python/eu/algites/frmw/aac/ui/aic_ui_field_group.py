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

from .aic_ui_field import AIcUiField

def _optional_display_text(value: AIcDisplayText | str | None) -> AIcDisplayText | None:
    if value == "":
        return None
    return normalize_display_text(value)

@dataclass(frozen=True, slots=True)
class AIcUiFieldGroup:
    id: str
    label: AIcDisplayText | None
    fields: tuple[AIcUiField, ...]
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _optional_display_text(self.label))
        object.__setattr__(self, "description", _optional_display_text(self.description))
