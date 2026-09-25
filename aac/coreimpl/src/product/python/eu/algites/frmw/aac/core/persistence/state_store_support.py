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

from .aic_in_memory_state_store import AIcInMemoryStateStore
from .aic_json_file_state_store import AIcJsonFileStateStore

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

def state_snapshot_to_raw(
    snapshot: Mapping[str, Mapping[str, AIcPersistedRecord]],
) -> dict[str, object]:
    return {
        "format_version": 1,
        "namespaces": {
            namespace: {
                key: {
                    "record_revision": record.record_revision,
                    "payload": _clone(dict(record.payload)),
                }
                for key, record in values.items()
            }
            for namespace, values in snapshot.items()
        },
    }

def state_snapshot_from_raw(raw: Mapping[str, object]) -> Mapping[str, Mapping[str, AIcPersistedRecord]]:
    if int(raw.get("format_version", 0)) != 1 or not isinstance(raw.get("namespaces"), Mapping):
        raise AIxPersistenceError("Core state recovery snapshot is invalid")
    result: dict[str, dict[str, AIcPersistedRecord]] = {}
    for namespace, values in raw["namespaces"].items():
        if not isinstance(values, Mapping):
            raise AIxPersistenceError(f"Core state recovery namespace {namespace!r} is invalid")
        target: dict[str, AIcPersistedRecord] = {}
        for key, envelope in values.items():
            if not isinstance(envelope, Mapping) or not isinstance(envelope.get("payload"), Mapping):
                raise AIxPersistenceError(f"Core state recovery record {namespace}:{key} is invalid")
            target[str(key)] = AIcPersistedRecord(
                str(namespace), str(key), envelope["record_revision"], _clone(dict(envelope["payload"]))
            )
        result[str(namespace)] = target
    return result

def state_put_mutation(
    store: AIiStateStore,
    namespace: str,
    key: str,
    value: Mapping[str, object],
) -> AIcStateMutation:
    current = store.get_record(namespace, key)
    return AIcStateMutation.put(
        namespace,
        key,
        value,
        expected_record_revision=None if current is None else current.record_revision,
        expect_absent=current is None,
    )

def state_delete_mutation(store: AIiStateStore, namespace: str, key: str) -> AIcStateMutation:
    current = store.get_record(namespace, key)
    return AIcStateMutation.delete(
        namespace,
        key,
        expected_record_revision=None if current is None else current.record_revision,
    )
