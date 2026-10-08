from __future__ import annotations

from eu.algites.frmw.aac.core.packages.aiig_active_package_set_1 import AIigActivePackageSet_1
from eu.algites.frmw.aac.core.packages.aiig_active_package_set_selections_items_1 import AIigActivePackageSetSelectionsItems_1
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from eu.algites.frmw.aac.core.packages.api import (
    AIcPackageSelection,
    AIcPackageSelectionManifest,
    AIcPackageStoreLayout,
    AIcPackageTransactionRecovery,
    AIcStoredPackage,
)
from eu.algites.frmw.aac.core.persistence.api import (
    AIcPersistenceTransactionRead,
    AIcPersistenceTransactionWrite,
    AInPersistenceTransactionPhase,
    AIiStateStore,
)
from eu.algites.frmw.aac.core.persistence.durable import AIcInterProcessFileLock, atomic_write_json
from eu.algites.frmw.aac.core.implementation.errors import AIxPersistenceError, AIxPersistenceRevisionConflict
from eu.algites.frmw.aac.core.persistence.state_store_support import state_snapshot_from_raw, state_snapshot_to_raw
from eu.algites.frmw.aac.core.persistence.transactions import AIcDurableTransactionJournal

def _selection_to_raw(item: AIcPackageSelection) -> dict[str, object]:
    return {
        AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__APPLICATION_SCOPE_ID: item.application_scope_id,
        AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__COMPONENT_ID: item.component_id,
        AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__COMPONENT_VERSION: item.component_version,
        AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__SHA256: item.sha256,
        AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__SELECTED_AT: item.selected_at,
        AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__PREVIOUS_SHA256: item.previous_sha256,
        AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__PREVIOUS_VERSION: item.previous_version,
    }

def _selection_from_raw(raw: Mapping[str, object]) -> AIcPackageSelection:
    return AIcPackageSelection(
        str(raw[AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__APPLICATION_SCOPE_ID]),
        str(raw[AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__COMPONENT_ID]),
        int(raw[AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__COMPONENT_VERSION]),
        str(raw[AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__SHA256]),
        str(raw[AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__SELECTED_AT]),
        str(raw[AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__PREVIOUS_SHA256]) if raw.get(AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__PREVIOUS_SHA256) is not None else None,
        int(raw[AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__PREVIOUS_VERSION]) if raw.get(AIigActivePackageSetSelectionsItems_1.SCHEMA_FIELD_NAME__PREVIOUS_VERSION) is not None else None,
    )

def manifest_to_raw(manifest: AIcPackageSelectionManifest) -> dict[str, object]:
    return {
        AIigActivePackageSet_1.SCHEMA_FIELD_NAME__FORMAT_VERSION: 1,
        AIigActivePackageSet_1.SCHEMA_FIELD_NAME__RECORD_REVISION: manifest.record_revision,
        AIigActivePackageSet_1.SCHEMA_FIELD_NAME__LAST_TRANSACTION_ID: manifest.last_transaction_id,
        AIigActivePackageSet_1.SCHEMA_FIELD_NAME__SELECTIONS: [_selection_to_raw(item) for item in manifest.selections],
    }

def manifest_from_raw(raw: Mapping[str, object]) -> AIcPackageSelectionManifest:
    format_version = int(raw.get(AIigActivePackageSet_1.SCHEMA_FIELD_NAME__FORMAT_VERSION, 0))
    if format_version != 1:
        raise AIxPersistenceError("active package set requires format_version 1")
    values = raw.get(AIigActivePackageSet_1.SCHEMA_FIELD_NAME__SELECTIONS, ())
    if not isinstance(values, list):
        raise AIxPersistenceError("active package set selections must be an array")
    revision = raw.get(AIigActivePackageSet_1.SCHEMA_FIELD_NAME__RECORD_REVISION, 0)
    return AIcPackageSelectionManifest(
        int(revision),
        tuple(_selection_from_raw(item) for item in values if isinstance(item, Mapping)),
        str(raw[AIigActivePackageSet_1.SCHEMA_FIELD_NAME__LAST_TRANSACTION_ID]) if raw.get(AIigActivePackageSet_1.SCHEMA_FIELD_NAME__LAST_TRANSACTION_ID) is not None else None,
    )

class AIcDurablePackageSelectionManifestStore:
    """Authoritative revisioned active package-set record."""

    def __init__(self, path: Path, *, mutation_lock_path: Path | None = None) -> None:
        self.path = path
        self.mutation_lock_path = mutation_lock_path or path.parent / "core.lock"

    def _read_unlocked(self) -> AIcPackageSelectionManifest:
        if not self.path.exists():
            return AIcPackageSelectionManifest(0)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AIxPersistenceError(f"cannot read active package set {self.path}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxPersistenceError(f"active package set {self.path} root must be an object")
        return manifest_from_raw(raw)

    def read(self) -> AIcPackageSelectionManifest:
        return self._read_unlocked()

    def write(
        self,
        manifest: AIcPackageSelectionManifest,
        *,
        expected_record_revision: int | None = None,
    ) -> None:
        with AIcInterProcessFileLock(self.mutation_lock_path):
            current = self._read_unlocked()
            if expected_record_revision is not None and current.record_revision != expected_record_revision:
                raise AIxPersistenceRevisionConflict(
                    "aac.packages.active-set", expected_record_revision, current.record_revision
                )
            atomic_write_json(self.path, manifest_to_raw(manifest))
