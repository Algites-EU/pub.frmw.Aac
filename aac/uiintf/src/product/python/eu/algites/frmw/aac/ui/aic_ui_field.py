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

from .aic_ui_choice import AIcUiChoice
from .aic_ui_configuration_scope import AIcUiConfigurationScope
from .ain_ui_field_type import AInUiFieldType

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
class AIcUiField:
    id: str
    label: AIcDisplayText
    field_type: AInUiFieldType
    value: object | None = None
    required: bool = False
    read_only: bool = False
    description: AIcDisplayText | None = None
    choices: tuple[AIcUiChoice, ...] = ()
    multiple: bool = False
    secret: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)
    accepted_configuration_scope_types: tuple[str, ...] = ()
    effective_configuration_scope: AIcUiConfigurationScope | None = None
    effective_configuration_provider_id: str | None = None
    value_source_kind: str | None = None
    policy_modes: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", _required_display_text(self.label))
        object.__setattr__(self, "description", _optional_display_text(self.description))
