from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class AInRecordRevisionKind(str, Enum):
    """Schema/persistence-contract declaration for record revision representation."""

    MONOTONIC_INTEGER = "MONOTONIC_INTEGER"
    OPAQUE_STRING = "OPAQUE_STRING"


class AInPersistenceCapability(str, Enum):
    READ = "READ"
    SINGLE_RECORD_CAS = "SINGLE_RECORD_CAS"
    MULTI_RECORD_TRANSACTION = "MULTI_RECORD_TRANSACTION"


class AInStateMutationKind(str, Enum):
    PUT = "PUT"
    DELETE = "DELETE"


@dataclass(frozen=True, slots=True)
class AIcPersistedRecord:
    namespace: str
    key: str
    record_revision: int | str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.namespace or not self.key:
            raise ValueError("persisted record namespace/key must not be empty")
        if isinstance(self.record_revision, int):
            if self.record_revision < 1:
                raise ValueError("integer record_revision must be >= 1")
        elif isinstance(self.record_revision, str):
            if not self.record_revision:
                raise ValueError("string record_revision must not be empty")
        else:
            raise TypeError("record_revision must be an integer or opaque string")


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


class AIiStateStore(ABC):
    """Core-owned normalized persistence adapter.

    Values are JSON-compatible normalized payloads wrapped by persistence-owned record revisions.
    The revision representation is declared by the persistence contract, not repeated as type
    metadata in each record. ``apply`` MUST commit all supplied mutations atomically or leave the
    store unchanged. Mutations carrying expected revisions MUST fail rather than overwrite a record
    that changed since it was read.
    """

    @property
    @abstractmethod
    def revision_kind(self) -> AInRecordRevisionKind: ...

    def capabilities(self) -> tuple[AInPersistenceCapability, ...]:
        return (
            AInPersistenceCapability.READ,
            AInPersistenceCapability.SINGLE_RECORD_CAS,
            AInPersistenceCapability.MULTI_RECORD_TRANSACTION,
        )

    @abstractmethod
    def get_record(self, namespace: str, key: str) -> AIcPersistedRecord | None: ...

    @abstractmethod
    def list_records(self, namespace: str) -> Mapping[str, AIcPersistedRecord]: ...

    def get(self, namespace: str, key: str) -> Mapping[str, object] | None:
        record = self.get_record(namespace, key)
        return None if record is None else record.payload

    def list(self, namespace: str) -> Mapping[str, Mapping[str, object]]:
        return {key: record.payload for key, record in self.list_records(namespace).items()}

    def put(self, namespace: str, key: str, value: Mapping[str, object]) -> AIcPersistedRecord:
        current = self.get_record(namespace, key)
        mutation = AIcStateMutation.put(
            namespace,
            key,
            value,
            expected_record_revision=None if current is None else current.record_revision,
            expect_absent=current is None,
        )
        return self.apply((mutation,))[0]

    def delete(self, namespace: str, key: str) -> None:
        current = self.get_record(namespace, key)
        if current is None:
            return
        self.apply((AIcStateMutation.delete(
            namespace,
            key,
            expected_record_revision=current.record_revision,
        ),))

    @abstractmethod
    def apply(
        self,
        mutations: tuple[AIcStateMutation, ...],
        *,
        read_expectations: tuple[AIcPersistenceReadExpectation, ...] = (),
    ) -> tuple[AIcPersistedRecord, ...]: ...

    @abstractmethod
    def snapshot(self) -> Mapping[str, Mapping[str, AIcPersistedRecord]]: ...

    @abstractmethod
    def restore(self, snapshot: Mapping[str, Mapping[str, AIcPersistedRecord]]) -> None: ...
