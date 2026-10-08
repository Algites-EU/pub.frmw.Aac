from __future__ import annotations

from eu.algites.frmw.aac.core.persistence.aiig_transaction_plan_1 import AIigTransactionPlan_1
from eu.algites.frmw.aac.core.persistence.aiig_transaction_plan_read_set_items_1 import AIigTransactionPlanReadSetItems_1
from eu.algites.frmw.aac.core.persistence.aiig_transaction_plan_write_set_items_1 import AIigTransactionPlanWriteSetItems_1
from eu.algites.frmw.aac.core.persistence.aiig_transaction_state_1 import AIigTransactionState_1
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4
from eu.algites.frmw.aac.core.persistence.api import (
    AIcPersistenceTransactionDescriptor,
    AIcPersistenceTransactionRead,
    AIcPersistenceTransactionWrite,
    AInPersistenceTransactionPhase,
)
from eu.algites.frmw.aac.core.persistence.durable import AIcInterProcessFileLock, atomic_write_json, durable_unlink, fsync_directory
from eu.algites.frmw.aac.core.implementation.errors import AIxPersistenceError

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _read_to_raw(item: AIcPersistenceTransactionRead) -> dict[str, object]:
    return {
        AIigTransactionPlanReadSetItems_1.SCHEMA_FIELD_NAME__RECORD_ID: item.record_id,
        AIigTransactionPlanReadSetItems_1.SCHEMA_FIELD_NAME__EXPECTED_RECORD_REVISION: item.expected_record_revision,
        AIigTransactionPlanReadSetItems_1.SCHEMA_FIELD_NAME__EXPECT_ABSENT: item.expect_absent,
    }

def _write_to_raw(item: AIcPersistenceTransactionWrite) -> dict[str, object]:
    return {
        AIigTransactionPlanWriteSetItems_1.SCHEMA_FIELD_NAME__RECORD_ID: item.record_id,
        AIigTransactionPlanWriteSetItems_1.SCHEMA_FIELD_NAME__OPERATION: item.operation,
        AIigTransactionPlanWriteSetItems_1.SCHEMA_FIELD_NAME__TARGET_RECORD_REVISION: item.target_record_revision,
        AIigTransactionPlanWriteSetItems_1.SCHEMA_FIELD_NAME__METADATA: dict(item.metadata),
    }

class AIcDurableTransactionJournal:
    """Generic durable journal for one Core-owned persistence domain.

    The journal records intent and recovery material. The transaction-specific authoritative commit
    marker remains a record owned by that transaction type. Recovery code MUST decide forward versus
    backward recovery from that marker rather than trusting a possibly stale journal phase alone.
    """

    def __init__(
        self, state_root: Path, transactions_subdirectory: str = "transactions",
        *, mutation_lock_path: Path | None = None,
    ) -> None:
        self.state_root = state_root
        self.transactions_root = state_root / transactions_subdirectory
        self.active_pointer = state_root / "active-transaction.json"
        self.mutation_lock_path = mutation_lock_path or state_root / "core.lock"

    def _transaction_dir(self, transaction_id: str) -> Path:
        return self.transactions_root / transaction_id

    def _plan_path(self, transaction_id: str) -> Path:
        return self._transaction_dir(transaction_id) / "transaction.json"

    def _state_path(self, transaction_id: str) -> Path:
        return self._transaction_dir(transaction_id) / "state.json"

    def recovery_payload_path(self, transaction_id: str, name: str) -> Path:
        if not name or "/" in name or "\\" in name or name in {".", ".."}:
            raise ValueError("recovery payload name must be one simple filename")
        return self._transaction_dir(transaction_id) / name

    def active_transaction_id(self) -> str | None:
        if not self.active_pointer.exists():
            return None
        try:
            raw = json.loads(self.active_pointer.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AIxPersistenceError(f"cannot read active transaction pointer: {exc}") from exc
        if not isinstance(raw, Mapping) or not raw.get("TransactionId"):
            raise AIxPersistenceError("active transaction pointer is invalid")
        return str(raw["TransactionId"])

    def begin(
        self,
        transaction_type: str,
        *,
        read_set: tuple[AIcPersistenceTransactionRead, ...] = (),
        write_set: tuple[AIcPersistenceTransactionWrite, ...] = (),
        metadata: Mapping[str, object] | None = None,
        recovery_payloads: Mapping[str, Mapping[str, object]] | None = None,
        validate_under_lock: Callable[[], None] | None = None,
    ) -> AIcPersistenceTransactionDescriptor:
        with AIcInterProcessFileLock(self.mutation_lock_path):
            active = self.active_transaction_id()
            if active is not None:
                raise AIxPersistenceError(f"persistence transaction {active} is already active")
            if validate_under_lock is not None:
                validate_under_lock()
            transaction_id = str(uuid4())
            descriptor = AIcPersistenceTransactionDescriptor(
                transaction_id,
                transaction_type,
                read_set,
                write_set,
                dict(metadata or {}),
            )
            directory = self._transaction_dir(transaction_id)
            directory.mkdir(parents=True, exist_ok=False)
            fsync_directory(directory.parent)
            plan = {
                AIigTransactionPlan_1.SCHEMA_FIELD_NAME__FORMAT_VERSION: 1,
                AIigTransactionPlan_1.SCHEMA_FIELD_NAME__TRANSACTION_ID: transaction_id,
                AIigTransactionPlan_1.SCHEMA_FIELD_NAME__TRANSACTION_TYPE: transaction_type,
                AIigTransactionPlan_1.SCHEMA_FIELD_NAME__CREATED_AT: _now(),
                AIigTransactionPlan_1.SCHEMA_FIELD_NAME__READ_SET: [_read_to_raw(item) for item in read_set],
                AIigTransactionPlan_1.SCHEMA_FIELD_NAME__WRITE_SET: [_write_to_raw(item) for item in write_set],
                AIigTransactionPlan_1.SCHEMA_FIELD_NAME__METADATA: dict(metadata or {}),
            }
            atomic_write_json(self._plan_path(transaction_id), plan)
            for name, payload in (recovery_payloads or {}).items():
                atomic_write_json(self.recovery_payload_path(transaction_id, name), dict(payload))
            self.write_phase(transaction_id, AInPersistenceTransactionPhase.PREPARED)
            atomic_write_json(self.active_pointer, {"FormatVersion": 1, "TransactionId": transaction_id})
            return descriptor

    def write_phase(
        self,
        transaction_id: str,
        phase: AInPersistenceTransactionPhase,
        diagnostics: tuple[str, ...] = (),
    ) -> None:
        atomic_write_json(self._state_path(transaction_id), {
            AIigTransactionState_1.SCHEMA_FIELD_NAME__FORMAT_VERSION: 1,
            AIigTransactionState_1.SCHEMA_FIELD_NAME__TRANSACTION_ID: transaction_id,
            AIigTransactionState_1.SCHEMA_FIELD_NAME__PHASE: phase.value,
            AIigTransactionState_1.SCHEMA_FIELD_NAME__UPDATED_AT: _now(),
            AIigTransactionState_1.SCHEMA_FIELD_NAME__DIAGNOSTICS: list(diagnostics),
        })

    def read_plan(self, transaction_id: str) -> Mapping[str, object]:
        try:
            raw = json.loads(self._plan_path(transaction_id).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AIxPersistenceError(f"cannot read transaction plan {transaction_id}: {exc}") from exc
        if not isinstance(raw, Mapping) or int(raw.get(AIigTransactionPlan_1.SCHEMA_FIELD_NAME__FORMAT_VERSION, 0)) != 1:
            raise AIxPersistenceError(f"transaction plan {transaction_id} is invalid")
        return raw

    def read_phase(self, transaction_id: str) -> AInPersistenceTransactionPhase:
        try:
            raw = json.loads(self._state_path(transaction_id).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AIxPersistenceError(f"cannot read transaction state {transaction_id}: {exc}") from exc
        return AInPersistenceTransactionPhase(str(raw[AIigTransactionState_1.SCHEMA_FIELD_NAME__PHASE]))

    def read_recovery_payload(self, transaction_id: str, name: str) -> Mapping[str, object]:
        try:
            raw = json.loads(self.recovery_payload_path(transaction_id, name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AIxPersistenceError(f"cannot read transaction recovery payload {name!r}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxPersistenceError(f"transaction recovery payload {name!r} must be an object")
        return raw

    def remove_recovery_payload(self, transaction_id: str, name: str) -> None:
        durable_unlink(self.recovery_payload_path(transaction_id, name))

    def finish(self, transaction_id: str) -> None:
        active = self.active_transaction_id()
        if active == transaction_id:
            durable_unlink(self.active_pointer)
