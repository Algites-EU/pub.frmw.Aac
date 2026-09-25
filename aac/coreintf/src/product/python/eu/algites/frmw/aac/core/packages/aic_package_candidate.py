from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText
from ..persistence.api import AInPersistenceTransactionPhase

from .aic_package_sidecar import AIcPackageSidecar

@dataclass(frozen=True, slots=True)
class AIcPackageCandidate:
    component_id: str
    component_version: int
    source_id: str
    artifact_uri: str
    artifact_filename: str
    package_format: str
    descriptor_path: str
    source_uri: str | None = None
    expected_sha256: str | None = None
    runtime_package: str | None = None
    verifier_id: str | None = None
    authentication_profile_id: str | None = None
    sidecars: tuple[AIcPackageSidecar, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
    name: AIcDisplayText | None = None
    description: AIcDisplayText | None = None

    def __post_init__(self) -> None:
        if not self.component_id or self.component_version < 1:
            raise ValueError("package candidate requires component id/version")
        if not self.source_id or not self.artifact_uri or not self.artifact_filename:
            raise ValueError("package candidate requires source/artifact information")
        if not self.package_format or not self.descriptor_path:
            raise ValueError("package candidate requires package_format and descriptor_path")
        if self.expected_sha256 is not None:
            digest = self.expected_sha256.lower()
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ValueError("expected_sha256 must contain exactly 64 hexadecimal characters")
            object.__setattr__(self, "expected_sha256", digest)
