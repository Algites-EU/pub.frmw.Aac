from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Generic, Mapping, TypeVar


T = TypeVar("T")


class AIiDataEntityView(ABC):
    """Marker base for generated versioned Data Entity view interfaces."""


@dataclass(frozen=True, slots=True)
class AIcDataEntityType(Generic[T]):
    schema_id: str
    view_version: int
    interface_type: type[T]

    def __post_init__(self) -> None:
        if not self.schema_id or self.view_version < 1:
            raise ValueError("data entity type requires schema id and view version >= 1")


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


@dataclass(frozen=True, slots=True)
class AIcDataEntityViewBinding(Generic[T]):
    data_type: AIcDataEntityType[T]
    codec: AIiDataEntityCodec[T]

    def __post_init__(self) -> None:
        if self.codec.schema_id != self.data_type.schema_id:
            raise ValueError("data entity codec schema id does not match view binding")
        if self.codec.schema_version != self.data_type.view_version:
            raise ValueError("data entity codec schema version does not match view binding")
        if self.codec.view_type is not self.data_type.interface_type:
            raise ValueError("data entity codec view type does not match view binding")


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
