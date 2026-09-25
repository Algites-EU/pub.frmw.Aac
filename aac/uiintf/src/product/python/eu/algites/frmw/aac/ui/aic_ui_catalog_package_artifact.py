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
class AIcUiCatalogPackageArtifact:
    source_id: str
    product_id: str
    technology_id: str
    component_id: str
    component_version: int
    artifact_id: str
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None
    publisher: str | None = None
    package_format: str | None = None
    artifact_uri: str | None = None
    sha256: str | None = None
    provides: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    entitlement_summary: tuple[str, ...] = ()
    entitlement_info_url: str | None = None
    homepage_url: str | None = None
    documentation_url: str | None = None
    icon_url: str | None = None
    downloaded: bool = False
    installed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _optional_display_text(self.name))
        object.__setattr__(self, "description", _optional_display_text(self.description))

    @property
    def identity(self) -> tuple[str, str, str, str, int, str]:
        return (
            self.source_id, self.product_id, self.technology_id,
            self.component_id, self.component_version, self.artifact_id,
        )
