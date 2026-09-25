from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class AInPersistenceTransactionPhase(str, Enum):
    PREPARED = "PREPARED"
    COMMIT_STARTED = "COMMIT_STARTED"
    COMMITTED = "COMMITTED"
    CLEANUP_COMPLETED = "CLEANUP_COMPLETED"
    ABORTED = "ABORTED"


@dataclass(frozen=True, slots=True)
class AIcPersistenceTransactionRead:
    record_id: str
    expected_record_revision: int | str | None = None
    expect_absent: bool = False

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValueError("transaction read record_id must not be empty")
        if self.expected_record_revision is not None and self.expect_absent:
            raise ValueError("transaction read cannot expect both a revision and absence")


@dataclass(frozen=True, slots=True)
class AIcPersistenceTransactionWrite:
    record_id: str
    operation: str
    target_record_revision: int | str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.record_id or not self.operation:
            raise ValueError("transaction write requires record_id and operation")


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
