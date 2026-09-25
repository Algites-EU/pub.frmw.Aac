from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Mapping, TypeVar
from enum import Enum

@dataclass(frozen=True, slots=True)
class AIcDataEntityMigrationResult:
    schema_id: str
    schema_version: int
    payload: Mapping[str, object]
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.schema_id or self.schema_version < 1:
            raise ValueError("data entity migration result requires schema id/version >= 1")
