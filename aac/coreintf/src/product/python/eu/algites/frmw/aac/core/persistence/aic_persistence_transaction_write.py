from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

@dataclass(frozen=True, slots=True)
class AIcPersistenceTransactionWrite:
    record_id: str
    operation: str
    target_record_revision: int | str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.record_id or not self.operation:
            raise ValueError("transaction write requires record_id and operation")
