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

from .aic_ui_configuration_scope import AIcUiConfigurationScope

@dataclass(frozen=True, slots=True)
class AIcUiConfigurationProviderOption:
    configuration_scope: AIcUiConfigurationScope
    configuration_provider_id: str
    technical_capabilities: tuple[str, ...] = ()
    authorized_capabilities: tuple[str, ...] = ()
    record_revision: str | int | None = None
    diagnostics: tuple[str, ...] = ()

    @property
    def can_write_value(self) -> bool:
        return "WRITE_VALUE" in self.authorized_capabilities

    @property
    def can_write_policy(self) -> bool:
        return "WRITE_POLICY" in self.authorized_capabilities
