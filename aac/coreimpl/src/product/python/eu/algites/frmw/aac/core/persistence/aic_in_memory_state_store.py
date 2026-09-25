from __future__ import annotations
import json
from pathlib import Path
from threading import RLock
from typing import Mapping
from eu.algites.frmw.aac.core.persistence.api import (
    AIcPersistedRecord,
    AIcPersistenceReadExpectation,
    AIcStateMutation,
    AInRecordRevisionKind,
    AInStateMutationKind,
    AIiStateStore,
)
from eu.algites.frmw.aac.core.persistence.durable import AIcInterProcessFileLock, atomic_write_json
from eu.algites.frmw.aac.core.implementation.errors import AIxPersistenceError, AIxPersistenceRevisionConflict

def _clone(value):
    return json.loads(json.dumps(value))

def _clone_record(record: AIcPersistedRecord) -> AIcPersistedRecord:
    return AIcPersistedRecord(record.namespace, record.key, record.record_revision, _clone(dict(record.payload)))

def _record_id(namespace: str, key: str) -> str:
    return f"{namespace}:{key}"

def _next_integer_revision(current: AIcPersistedRecord | None) -> int:
    if current is None:
        return 1
    if not isinstance(current.record_revision, int):
        raise AIxPersistenceError("Core-owned state store requires MONOTONIC_INTEGER record revisions")
    return current.record_revision + 1

def _validate_expectation(
    records: Mapping[str, Mapping[str, AIcPersistedRecord]],
    expectation: AIcPersistenceReadExpectation,
) -> None:
    current = records.get(expectation.namespace, {}).get(expectation.key)
    actual = None if current is None else current.record_revision
    if expectation.expect_absent:
        if current is not None:
            raise AIxPersistenceRevisionConflict(_record_id(expectation.namespace, expectation.key), None, actual)
        return
    if expectation.expected_record_revision is None:
        raise AIxPersistenceError(
            f"read expectation for {_record_id(expectation.namespace, expectation.key)!r} must declare a revision or absence"
        )
    if actual != expectation.expected_record_revision:
        raise AIxPersistenceRevisionConflict(
            _record_id(expectation.namespace, expectation.key), expectation.expected_record_revision, actual
        )

def _apply_mutations(
    records: dict[str, dict[str, AIcPersistedRecord]],
    mutations: tuple[AIcStateMutation, ...],
) -> tuple[AIcPersistedRecord, ...]:
    identities = [(item.namespace, item.key) for item in mutations]
    if len(identities) != len(set(identities)):
        raise AIxPersistenceError("one atomic state-store mutation may change each record at most once")
    written: list[AIcPersistedRecord] = []
    for mutation in mutations:
        namespace = records.setdefault(mutation.namespace, {})
        current = namespace.get(mutation.key)
        actual = None if current is None else current.record_revision
        record_id = _record_id(mutation.namespace, mutation.key)
        if mutation.expect_absent:
            if current is not None:
                raise AIxPersistenceRevisionConflict(record_id, None, actual)
        else:
            if current is not None:
                if mutation.expected_record_revision is None:
                    raise AIxPersistenceError(
                        f"mutation of existing record {record_id!r} requires expected_record_revision"
                    )
                if mutation.expected_record_revision != actual:
                    raise AIxPersistenceRevisionConflict(record_id, mutation.expected_record_revision, actual)
            elif mutation.expected_record_revision is not None:
                raise AIxPersistenceRevisionConflict(record_id, mutation.expected_record_revision, None)
            elif mutation.kind is AInStateMutationKind.PUT:
                raise AIxPersistenceError(f"creation of record {record_id!r} requires expect_absent=True")

        if mutation.kind is AInStateMutationKind.PUT:
            if mutation.value is None:
                raise AIxPersistenceError("PUT mutation requires a value")
            record = AIcPersistedRecord(
                mutation.namespace,
                mutation.key,
                _next_integer_revision(current),
                _clone(dict(mutation.value)),
            )
            namespace[mutation.key] = record
            written.append(record)
        elif mutation.kind is AInStateMutationKind.DELETE:
            namespace.pop(mutation.key, None)
        else:
            raise AIxPersistenceError(f"unsupported state mutation kind {mutation.kind!r}")
    return tuple(written)

class AIcInMemoryStateStore(AIiStateStore):
    def __init__(self) -> None:
        self._records: dict[str, dict[str, AIcPersistedRecord]] = {}
        self._lock = RLock()

    @property
    def revision_kind(self) -> AInRecordRevisionKind:
        return AInRecordRevisionKind.MONOTONIC_INTEGER

    def get_record(self, namespace: str, key: str) -> AIcPersistedRecord | None:
        with self._lock:
            value = self._records.get(namespace, {}).get(key)
            return _clone_record(value) if value is not None else None

    def list_records(self, namespace: str) -> Mapping[str, AIcPersistedRecord]:
        with self._lock:
            return {key: _clone_record(value) for key, value in self._records.get(namespace, {}).items()}

    def apply(
        self,
        mutations: tuple[AIcStateMutation, ...],
        *,
        read_expectations: tuple[AIcPersistenceReadExpectation, ...] = (),
    ) -> tuple[AIcPersistedRecord, ...]:
        with self._lock:
            for expectation in read_expectations:
                _validate_expectation(self._records, expectation)
            candidate = {
                namespace: {key: _clone_record(record) for key, record in values.items()}
                for namespace, values in self._records.items()
            }
            written = _apply_mutations(candidate, mutations)
            self._records = candidate
            return tuple(_clone_record(item) for item in written)

    def snapshot(self) -> Mapping[str, Mapping[str, AIcPersistedRecord]]:
        with self._lock:
            return {
                namespace: {key: _clone_record(record) for key, record in values.items()}
                for namespace, values in self._records.items()
            }

    def restore(self, snapshot: Mapping[str, Mapping[str, AIcPersistedRecord]]) -> None:
        with self._lock:
            self._records = {
                namespace: {key: _clone_record(record) for key, record in values.items()}
                for namespace, values in snapshot.items()
            }
