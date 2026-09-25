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

def _required_display_text(value: AIcDisplayText | str) -> AIcDisplayText:
    normalized = normalize_display_text(value)
    if normalized is None:
        raise ValueError("required display text is missing")
    return normalized

def _optional_display_text(value: AIcDisplayText | str | None) -> AIcDisplayText | None:
    if value == "":
        return None
    return normalize_display_text(value)

@dataclass(frozen=True, slots=True)
class AIcUiChoice:
    value: object
    label: AIcDisplayText
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _required_display_text(self.label))
        object.__setattr__(self, "description", _optional_display_text(self.description))
