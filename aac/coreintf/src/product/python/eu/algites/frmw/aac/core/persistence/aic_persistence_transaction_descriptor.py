from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .aic_persistence_transaction_read import AIcPersistenceTransactionRead
from .aic_persistence_transaction_write import AIcPersistenceTransactionWrite

@dataclass(frozen=True, slots=True)
class AIcPersistenceTransactionDescriptor:
    transaction_id: str
    transaction_type: str
    read_set: tuple[AIcPersistenceTransactionRead, ...]
    write_set: tuple[AIcPersistenceTransactionWrite, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.transaction_id or not self.transaction_type:
            raise ValueError("persistence transaction requires id and type")
        read_ids = [item.record_id for item in self.read_set]
        write_ids = [item.record_id for item in self.write_set]
        if len(read_ids) != len(set(read_ids)) or len(write_ids) != len(set(write_ids)):
            raise ValueError("transaction read/write sets must be unique by record_id")
