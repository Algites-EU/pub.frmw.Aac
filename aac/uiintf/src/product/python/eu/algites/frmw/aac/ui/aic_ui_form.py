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

from .aic_ui_configuration_provider_option import AIcUiConfigurationProviderOption
from .aic_ui_configuration_scope import AIcUiConfigurationScope
from .aic_ui_field import AIcUiField
from .aic_ui_field_group import AIcUiFieldGroup

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
class AIcUiForm:
    id: str
    title: AIcDisplayText
    groups: tuple[AIcUiFieldGroup, ...]
    configuration_scopes: tuple[AIcUiConfigurationScope, ...] = ()
    active_configuration_profile_id: str | None = None
    configuration_provider_options: tuple[AIcUiConfigurationProviderOption, ...] = ()
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _required_display_text(self.title))
        object.__setattr__(self, "description", _optional_display_text(self.description))

    @property
    def fields(self) -> tuple[AIcUiField, ...]:
        return tuple(field for group in self.groups for field in group.fields)
