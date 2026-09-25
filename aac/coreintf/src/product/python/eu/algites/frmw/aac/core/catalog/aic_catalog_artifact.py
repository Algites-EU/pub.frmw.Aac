from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..capability.api import AInConsumerCardinality
from ..descriptor.api import AIcCapabilityEntitlementDescriptor, AIcEntitlementLicensingScopeDescriptor
from ..presentation.api import AIcDisplayText
from ..packages.api import AIcPackageSidecar

from .aic_catalog_artifact_locator import AIcCatalogArtifactLocator

@dataclass(frozen=True, slots=True)
class AIcCatalogArtifact:
    id: str
    locator: AIcCatalogArtifactLocator
    artifact_filename: str
    package_format: str
    descriptor_path: str
    sha256: str
    runtime_package: str | None = None
    verifier_id: str | None = None
    authentication_profile_id: str | None = None
    sidecars: tuple[AIcPackageSidecar, ...] = ()
    platforms: tuple[str, ...] = ()
    architectures: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.artifact_filename or not self.package_format or not self.descriptor_path:
            raise ValueError("catalog artifact requires id/filename/package_format/descriptor_path")
        digest = self.sha256.lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("catalog artifact sha256 must contain exactly 64 hexadecimal characters")
        object.__setattr__(self, "sha256", digest)
        if len(self.platforms) != len(set(self.platforms)) or len(self.architectures) != len(set(self.architectures)):
            raise ValueError("catalog artifact platform/architecture selectors must be unique")
