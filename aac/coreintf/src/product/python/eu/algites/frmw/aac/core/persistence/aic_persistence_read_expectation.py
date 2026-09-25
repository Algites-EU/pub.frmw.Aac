from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

@dataclass(frozen=True, slots=True)
class AIcPersistenceReadExpectation:
    namespace: str
    key: str
    expected_record_revision: int | str | None = None
    expect_absent: bool = False

    def __post_init__(self) -> None:
        if not self.namespace or not self.key:
            raise ValueError("persistence read expectation namespace/key must not be empty")
        if self.expected_record_revision is not None and self.expect_absent:
            raise ValueError("read expectation cannot expect both a revision and absence")
