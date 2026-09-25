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

from .aic_ui_display import AIcUiDisplay
from .aic_ui_form import AIcUiForm

def _optional_display_text(value: AIcDisplayText | str | None) -> AIcDisplayText | None:
    if value == "":
        return None
    return normalize_display_text(value)

@dataclass(frozen=True, slots=True)
class AIcUiPanel:
    id: str
    title: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    displays: tuple[AIcUiDisplay, ...] = ()
    forms: tuple[AIcUiForm, ...] = ()
    panels: tuple["AIcUiPanel", ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _optional_display_text(self.title))
        object.__setattr__(self, "description", _optional_display_text(self.description))
