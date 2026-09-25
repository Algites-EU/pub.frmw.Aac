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
class AIcUiRequirement:
    consumer_instance_id: str
    consumer_instance_name: AIcDisplayText
    requirement_id: str
    capability_id: str
    versions: tuple[int, ...]
    cardinality: str
    mandatory: bool
    selected_provider_instance_ids: tuple[str, ...] = ()
    requested_authorizations: tuple[str, ...] = ()
    granted_authorizations: tuple[str, ...] = ()
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "consumer_instance_name", _required_display_text(self.consumer_instance_name))
        object.__setattr__(self, "name", _optional_display_text(self.name))
        object.__setattr__(self, "description", _optional_display_text(self.description))
