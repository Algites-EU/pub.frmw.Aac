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

def _required_display_content(value: AIcDisplayContent | str) -> AIcDisplayContent:
    normalized = normalize_display_content(value)
    if normalized is None:
        raise ValueError("required display content is missing")
    return normalized

@dataclass(frozen=True, slots=True)
class AIcUiDisplay:
    id: str
    content: AIcDisplayContent
    title: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", _required_display_content(self.content))
        object.__setattr__(self, "title", _optional_display_text(self.title))
