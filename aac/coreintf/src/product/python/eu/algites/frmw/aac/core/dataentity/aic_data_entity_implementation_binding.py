from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Generic, Mapping, TypeVar

@dataclass(frozen=True, slots=True)
class AIcDataEntityImplementationBinding:
    schema_id: str
    canonical_schema_version: int
    implementation_type: type[object]
    factory: Callable[[], object]
    supported_view_versions: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.schema_id or self.canonical_schema_version < 1:
            raise ValueError("data entity implementation binding requires schema id/version")
        if not self.supported_view_versions or any(version < 1 for version in self.supported_view_versions):
            raise ValueError("data entity implementation must support at least one view version")
        if len(self.supported_view_versions) != len(set(self.supported_view_versions)):
            raise ValueError("supported data entity view versions must be unique")
        if self.canonical_schema_version not in self.supported_view_versions:
            raise ValueError("canonical schema version must be a supported runtime view")
