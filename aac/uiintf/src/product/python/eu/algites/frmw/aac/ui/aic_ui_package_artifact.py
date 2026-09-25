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
class AIcUiPackageArtifact:
    component_id: str
    component_version: int
    sha256: str
    state: str
    selected_application_scope_ids: tuple[str, ...] = ()
    source_id: str | None = None
    signer_identity: str | None = None
    artifact_path: str | None = None

    @property
    def identity(self) -> tuple[str, int, str]:
        return self.component_id, self.component_version, self.sha256

    @property
    def selected(self) -> bool:
        return bool(self.selected_application_scope_ids)
