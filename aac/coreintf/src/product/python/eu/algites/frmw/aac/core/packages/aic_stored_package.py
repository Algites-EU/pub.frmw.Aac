from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

from .aic_package_provenance import AIcPackageProvenance
from .ain_stored_package_state import AInStoredPackageState

@dataclass(frozen=True, slots=True)
class AIcStoredPackage:
    component_id: str
    component_version: int
    sha256: str
    state: AInStoredPackageState
    artifact_path: str
    package_format: str
    descriptor_path: str
    runtime_package: str | None
    provenance: AIcPackageProvenance
    sidecar_paths: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    @property
    def identity(self) -> tuple[str, int, str]:
        return self.component_id, self.component_version, self.sha256
