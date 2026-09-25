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
class AIcUiProviderInstance:
    id: str
    component_id: str
    provider_definition_id: str
    name: AIcDisplayText
    capabilities: tuple[tuple[str, tuple[int, ...]], ...]
    access_mode: str
    state: str
    configuration_schema: str | None
    readiness_state: str | None = None
    readiness_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _required_display_text(self.name))

    def supports_capability(self, capability_id: str) -> bool:
        return any(value[0] == capability_id for value in self.capabilities)

    @property
    def capabilities_text(self) -> str:
        return ", ".join(
            f"{capability_id} [{', '.join(str(version) for version in versions)}]"
            for capability_id, versions in self.capabilities
        )
