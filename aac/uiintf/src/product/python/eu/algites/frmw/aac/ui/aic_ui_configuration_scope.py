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
class AIcUiConfigurationScope:
    type: str
    id: str | None = None
    editable: bool = False
    policy_authority: bool = False

    @property
    def key(self) -> str:
        return self.type if self.id is None else f"{self.type}({self.id})"
