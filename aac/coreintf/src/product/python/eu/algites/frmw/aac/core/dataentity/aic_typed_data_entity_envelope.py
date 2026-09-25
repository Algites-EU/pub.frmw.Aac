from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Mapping, TypeVar
from enum import Enum

from .aic_data_entity_identity import AIcDataEntityIdentity
from .ain_data_entity_state import AInDataEntityState

T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class AIcTypedDataEntityEnvelope(Generic[T]):
    uid: str
    schema_id: str
    stored_schema_version: int
    canonical_schema_version: int
    record_revision: int | str
    state: AInDataEntityState
    entity: T

    def __post_init__(self) -> None:
        if not self.uid or not self.schema_id:
            raise ValueError("typed data entity envelope requires non-empty uid and schema_id")
        if self.stored_schema_version < 1 or self.canonical_schema_version < 1:
            raise ValueError("typed data entity schema versions must be >= 1")

    @property
    def identity(self) -> AIcDataEntityIdentity:
        return AIcDataEntityIdentity(self.schema_id, self.uid)
