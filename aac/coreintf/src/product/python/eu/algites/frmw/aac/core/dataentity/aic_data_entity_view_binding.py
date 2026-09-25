from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Generic, Mapping, TypeVar

from .aic_data_entity_type import AIcDataEntityType
from .aii_data_entity_codec import AIiDataEntityCodec

T = TypeVar("T")

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
