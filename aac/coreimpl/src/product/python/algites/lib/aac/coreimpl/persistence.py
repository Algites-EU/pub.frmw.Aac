from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Mapping

from algites.lib.aac.coreintf.persistence import (
    AIcPersistedRecord,
    AIcPersistenceReadExpectation,
    AIcStateMutation,
    AInRecordRevisionKind,
    AInStateMutationKind,
    AIiStateStore,
)

from .durable import AIcInterProcessFileLock, atomic_write_json
from .errors import AIxPersistenceError, AIxPersistenceRevisionConflict


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


class AIcJsonFileStateStore(AIiStateStore):
    """Revisioned atomic JSON persistence adapter for Core-owned normalized state."""

    def __init__(self, path: str | Path, *, mutation_lock_path: str | Path | None = None) -> None:
        self.path = Path(path)
        self.mutation_lock_path = Path(mutation_lock_path) if mutation_lock_path is not None else self.path.parent / "core.lock"
        self._lock = RLock()

    @property
    def revision_kind(self) -> AInRecordRevisionKind:
        return AInRecordRevisionKind.MONOTONIC_INTEGER

    def _read(self) -> dict[str, dict[str, AIcPersistedRecord]]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AIxPersistenceError(f"cannot read state store {self.path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise AIxPersistenceError(f"state store {self.path} root must be an object")
        if int(raw.get("format_version", 0)) == 2:
            raw_records = raw.get("records", {})
            if not isinstance(raw_records, Mapping):
                raise AIxPersistenceError(f"state store {self.path} records must be an object")
            result: dict[str, dict[str, AIcPersistedRecord]] = {}
            for namespace, values in raw_records.items():
                if not isinstance(values, Mapping):
                    raise AIxPersistenceError(f"state store namespace {namespace!r} must be an object")
                target: dict[str, AIcPersistedRecord] = {}
                for key, envelope in values.items():
                    if not isinstance(envelope, Mapping) or not isinstance(envelope.get("payload"), Mapping):
                        raise AIxPersistenceError(f"state record {namespace}:{key} is invalid")
                    target[str(key)] = AIcPersistedRecord(
                        str(namespace), str(key), int(envelope["record_revision"]), _clone(dict(envelope["payload"]))
                    )
                result[str(namespace)] = target
            return result

        # Build <= 19 stored raw payloads without revisions. Treat each legacy record as revision 1;
        # the next successful mutation rewrites the whole store in the canonical v2 envelope form.
        result = {}
        for namespace, values in raw.items():
            if not isinstance(values, Mapping):
                raise AIxPersistenceError(f"legacy state store namespace {namespace!r} must be an object")
            result[str(namespace)] = {
                str(key): AIcPersistedRecord(str(namespace), str(key), 1, _clone(dict(payload)))
                for key, payload in values.items() if isinstance(payload, Mapping)
            }
        return result

    def _write(self, records: Mapping[str, Mapping[str, AIcPersistedRecord]]) -> None:
        raw = {
            "format_version": 2,
            "revision_kind": AInRecordRevisionKind.MONOTONIC_INTEGER.value,
            "records": {
                namespace: {
                    key: {
                        "record_revision": record.record_revision,
                        "payload": _clone(dict(record.payload)),
                    }
                    for key, record in values.items()
                }
                for namespace, values in records.items()
            },
        }
        atomic_write_json(self.path, raw)

    def get_record(self, namespace: str, key: str) -> AIcPersistedRecord | None:
        with self._lock:
            value = self._read().get(namespace, {}).get(key)
            return _clone_record(value) if value is not None else None

    def list_records(self, namespace: str) -> Mapping[str, AIcPersistedRecord]:
        with self._lock:
            return {key: _clone_record(value) for key, value in self._read().get(namespace, {}).items()}

    def apply(
        self,
        mutations: tuple[AIcStateMutation, ...],
        *,
        read_expectations: tuple[AIcPersistenceReadExpectation, ...] = (),
    ) -> tuple[AIcPersistedRecord, ...]:
        with self._lock, AIcInterProcessFileLock(self.mutation_lock_path):
            records = self._read()
            for expectation in read_expectations:
                _validate_expectation(records, expectation)
            candidate = {
                namespace: {key: _clone_record(record) for key, record in values.items()}
                for namespace, values in records.items()
            }
            written = _apply_mutations(candidate, mutations)
            self._write(candidate)
            return tuple(_clone_record(item) for item in written)

    def snapshot(self) -> Mapping[str, Mapping[str, AIcPersistedRecord]]:
        with self._lock:
            return {
                namespace: {key: _clone_record(record) for key, record in values.items()}
                for namespace, values in self._read().items()
            }

    def restore(self, snapshot: Mapping[str, Mapping[str, AIcPersistedRecord]]) -> None:
        with self._lock, AIcInterProcessFileLock(self.mutation_lock_path):
            self._write({
                namespace: {key: _clone_record(record) for key, record in values.items()}
                for namespace, values in snapshot.items()
            })


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
