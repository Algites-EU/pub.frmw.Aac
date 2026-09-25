from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

@dataclass(frozen=True, slots=True)
class AIcPersistedRecord:
    namespace: str
    key: str
    record_revision: int | str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.namespace or not self.key:
            raise ValueError("persisted record namespace/key must not be empty")
        if isinstance(self.record_revision, int):
            if self.record_revision < 1:
                raise ValueError("integer record_revision must be >= 1")
        elif isinstance(self.record_revision, str):
            if not self.record_revision:
                raise ValueError("string record_revision must not be empty")
        else:
            raise TypeError("record_revision must be an integer or opaque string")
