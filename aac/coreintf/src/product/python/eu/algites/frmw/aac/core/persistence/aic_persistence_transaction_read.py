from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

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
