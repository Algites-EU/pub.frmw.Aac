from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Mapping, TypeVar
from enum import Enum

@dataclass(frozen=True, slots=True)
class AIcDataEntityReferenceDefinition:
    source_schema_id: str
    source_schema_version: int
    schema_path: tuple[str, ...]
    target_schema_id: str

    def __post_init__(self) -> None:
        if not self.source_schema_id or not self.target_schema_id:
            raise ValueError("data entity reference definition requires source and target schema ids")
        if self.source_schema_version < 1:
            raise ValueError("data entity reference source schema version must be >= 1")
