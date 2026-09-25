from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Mapping, TypeVar
from enum import Enum

from .aic_data_entity_envelope import AIcDataEntityEnvelope

@dataclass(frozen=True, slots=True)
class AIcDataEntityMigrationRequest:
    source: AIcDataEntityEnvelope
    target_schema_version: int

    def __post_init__(self) -> None:
        if self.target_schema_version < 1:
            raise ValueError("target data entity schema version must be >= 1")
