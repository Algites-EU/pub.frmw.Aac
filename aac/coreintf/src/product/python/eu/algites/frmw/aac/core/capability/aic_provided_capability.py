from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from ..presentation.api import AIcDisplayText

@dataclass(frozen=True, slots=True)
class AIcProvidedCapability:
    id: str
    versions: tuple[int, ...]
    binding_qualifier_profiles: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("provided capability id must not be empty")
        if not self.versions or any(version < 1 for version in self.versions):
            raise ValueError("provided capability must declare at least one version >= 1")
        if len(self.versions) != len(set(self.versions)):
            raise ValueError("provided capability versions must be unique")
        if any(not isinstance(item, Mapping) for item in self.binding_qualifier_profiles):
            raise ValueError("provided capability binding qualifier profiles must be mappings")

    @property
    def latest_version(self) -> int:
        return max(self.versions)
