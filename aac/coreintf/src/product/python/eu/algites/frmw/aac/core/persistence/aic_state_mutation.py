from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .ain_state_mutation_kind import AInStateMutationKind

@dataclass(frozen=True, slots=True)
class AIcStateMutation:
    kind: AInStateMutationKind
    namespace: str
    key: str
    value: Mapping[str, object] | None = None
    expected_record_revision: int | str | None = None
    expect_absent: bool = False

    def __post_init__(self) -> None:
        if not self.namespace or not self.key:
            raise ValueError("state mutation namespace/key must not be empty")
        if self.expected_record_revision is not None and self.expect_absent:
            raise ValueError("state mutation cannot expect both a revision and absence")
        if self.kind is AInStateMutationKind.PUT and self.value is None:
            raise ValueError("PUT mutation requires a value")
        if self.kind is AInStateMutationKind.DELETE and self.value is not None:
            raise ValueError("DELETE mutation must not carry a value")

    @staticmethod
    def put(
        namespace: str,
        key: str,
        value: Mapping[str, object],
        *,
        expected_record_revision: int | str | None = None,
        expect_absent: bool = False,
    ) -> "AIcStateMutation":
        return AIcStateMutation(
            AInStateMutationKind.PUT,
            namespace,
            key,
            value,
            expected_record_revision,
            expect_absent,
        )

    @staticmethod
    def delete(
        namespace: str,
        key: str,
        *,
        expected_record_revision: int | str | None = None,
    ) -> "AIcStateMutation":
        return AIcStateMutation(
            AInStateMutationKind.DELETE,
            namespace,
            key,
            None,
            expected_record_revision,
            False,
        )
