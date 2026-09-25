from __future__ import annotations
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

from .aic_durable_transaction_journal import AIcDurableTransactionJournal

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _read_to_raw(item: AIcPersistenceTransactionRead) -> dict[str, object]:
    return {
        "record_id": item.record_id,
        "expected_record_revision": item.expected_record_revision,
        "expect_absent": item.expect_absent,
    }

def _write_to_raw(item: AIcPersistenceTransactionWrite) -> dict[str, object]:
    return {
        "record_id": item.record_id,
        "operation": item.operation,
        "target_record_revision": item.target_record_revision,
        "metadata": dict(item.metadata),
    }
