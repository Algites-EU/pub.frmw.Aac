from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Mapping, TypeVar
from enum import Enum

@dataclass(frozen=True, slots=True)
class AIcDataEntityIdentity:
    schema_id: str
    uid: str

    def __post_init__(self) -> None:
        if not self.schema_id or not self.uid:
            raise ValueError("data entity identity requires non-empty schema_id and uid")
