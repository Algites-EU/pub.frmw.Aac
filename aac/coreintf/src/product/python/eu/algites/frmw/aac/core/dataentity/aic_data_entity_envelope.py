from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Mapping, TypeVar
from enum import Enum

from .aic_data_entity_identity import AIcDataEntityIdentity
from .ain_data_entity_state import AInDataEntityState

@dataclass(frozen=True, slots=True)
class AIcDataEntityEnvelope:
    uid: str
    schema_id: str
    schema_version: int
    record_revision: int | str
    state: AInDataEntityState
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.uid or not self.schema_id:
            raise ValueError("data entity envelope requires non-empty uid and schema_id")
        if self.schema_version < 1:
            raise ValueError("data entity schema_version must be >= 1")
        if isinstance(self.record_revision, int):
            if self.record_revision < 1:
                raise ValueError("integer data entity record_revision must be >= 1")
        elif isinstance(self.record_revision, str):
            if not self.record_revision:
                raise ValueError("string data entity record_revision must not be empty")
        else:
            raise TypeError("data entity record_revision must be an integer or opaque string")
        if not isinstance(self.payload, Mapping):
            raise TypeError("data entity payload must be a JSON object mapping")

    @property
    def identity(self) -> AIcDataEntityIdentity:
        return AIcDataEntityIdentity(self.schema_id, self.uid)
