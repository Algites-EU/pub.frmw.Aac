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

@dataclass(frozen=True, slots=True)
class AIcUiUpgradeDiagnostic:
    component_id: str
    message: AIcDisplayText
    consumer_instance_id: str | None = None
    requirement_id: str | None = None
    capability_id: str | None = None
    consumer_versions: tuple[int, ...] = ()
    provider_versions: tuple[int, ...] = ()
    available_provider_component_ids: tuple[str, ...] = ()
    blocking: bool = True
    code: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "message", _required_display_text(self.message))
