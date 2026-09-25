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
class AIcUiComponent:
    id: str
    version: int
    provider_definition_ids: tuple[str, ...]
    permission_count: int = 0
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    origin: str | None = None
    readiness_state: str | None = None
    readiness_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _optional_display_text(self.name))
        object.__setattr__(self, "description", _optional_display_text(self.description))
