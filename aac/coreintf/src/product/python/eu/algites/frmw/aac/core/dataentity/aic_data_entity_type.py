from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Generic, Mapping, TypeVar

T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class AIcDataEntityType(Generic[T]):
    schema_id: str
    view_version: int
    interface_type: type[T]

    def __post_init__(self) -> None:
        if not self.schema_id or self.view_version < 1:
            raise ValueError("data entity type requires schema id and view version >= 1")
