from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Generic, Mapping, TypeVar

T = TypeVar("T")

class AIiDataEntityCodec(ABC, Generic[T]):
    """Version-specific codec between one schema view and the canonical JSON object representation."""

    schema_id: str
    schema_version: int
    view_type: type[T]

    @abstractmethod
    def serialize(self, value: T) -> Mapping[str, object]:
        """Serialize exactly this codec's versioned view."""

    @abstractmethod
    def deserialize_into(self, payload: Mapping[str, object], target: T) -> None:
        """Apply one stored schema-version payload through this view onto a current implementation object."""
