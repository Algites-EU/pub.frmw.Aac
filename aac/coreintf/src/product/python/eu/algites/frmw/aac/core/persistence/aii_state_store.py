from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .aic_persisted_record import AIcPersistedRecord
from .aic_persistence_read_expectation import AIcPersistenceReadExpectation
from .aic_state_mutation import AIcStateMutation
from .ain_persistence_capability import AInPersistenceCapability
from .ain_record_revision_kind import AInRecordRevisionKind

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
