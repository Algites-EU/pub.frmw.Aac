from __future__ import annotations
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

from .aic_durable_package_selection_manifest_store import AIcDurablePackageSelectionManifestStore
from .aic_package_replacement_journal_handle import AIcPackageReplacementJournalHandle
from .aic_package_replacement_journal import AIcPackageReplacementJournal

def _selection_to_raw(item: AIcPackageSelection) -> dict[str, object]:
    return {
        "application_scope_id": item.application_scope_id,
        "component_id": item.component_id,
        "component_version": item.component_version,
        "sha256": item.sha256,
        "selected_at": item.selected_at,
        "previous_sha256": item.previous_sha256,
        "previous_version": item.previous_version,
    }

def _selection_from_raw(raw: Mapping[str, object]) -> AIcPackageSelection:
    return AIcPackageSelection(
        str(raw["application_scope_id"]),
        str(raw["component_id"]),
        int(raw["component_version"]),
        str(raw["sha256"]),
        str(raw["selected_at"]),
        str(raw["previous_sha256"]) if raw.get("previous_sha256") is not None else None,
        int(raw["previous_version"]) if raw.get("previous_version") is not None else None,
    )

def manifest_to_raw(manifest: AIcPackageSelectionManifest) -> dict[str, object]:
    return {
        "format_version": 1,
        "record_revision": manifest.record_revision,
        "last_transaction_id": manifest.last_transaction_id,
        "selections": [_selection_to_raw(item) for item in manifest.selections],
    }

def manifest_from_raw(raw: Mapping[str, object]) -> AIcPackageSelectionManifest:
    format_version = int(raw.get("format_version", 0))
    if format_version != 1:
        raise AIxPersistenceError("active package set requires format_version 1")
    values = raw.get("selections", ())
    if not isinstance(values, list):
        raise AIxPersistenceError("active package set selections must be an array")
    revision = raw.get("record_revision", 0)
    return AIcPackageSelectionManifest(
        int(revision),
        tuple(_selection_from_raw(item) for item in values if isinstance(item, Mapping)),
        str(raw["last_transaction_id"]) if raw.get("last_transaction_id") is not None else None,
    )
