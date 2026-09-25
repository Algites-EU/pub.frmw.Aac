from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

from .aic_package_sidecar import AIcPackageSidecar

@dataclass(frozen=True, slots=True)
class AIcWorkspaceComponentLockEntry:
    component_id: str
    component_version: int
    sha256: str
    source_id: str
    artifact_uri: str
    artifact_filename: str
    package_format: str
    descriptor_path: str
    source_uri: str | None = None
    runtime_package: str | None = None
    verifier_id: str | None = None
    sidecars: tuple[AIcPackageSidecar, ...] = ()

    def __post_init__(self) -> None:
        if not self.component_id or self.component_version < 1:
            raise ValueError("workspace component lock entry requires component id/version")
        digest = self.sha256.lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("workspace component lock sha256 must contain exactly 64 hexadecimal characters")
        object.__setattr__(self, "sha256", digest)
