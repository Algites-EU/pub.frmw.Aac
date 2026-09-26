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
        "ApplicationScopeId": item.application_scope_id,
        "ComponentId": item.component_id,
        "ComponentVersion": item.component_version,
        "Sha256": item.sha256,
        "SelectedAt": item.selected_at,
        "PreviousSha256": item.previous_sha256,
        "PreviousVersion": item.previous_version,
    }

def _selection_from_raw(raw: Mapping[str, object]) -> AIcPackageSelection:
    return AIcPackageSelection(
        str(raw["ApplicationScopeId"]),
        str(raw["ComponentId"]),
        int(raw["ComponentVersion"]),
        str(raw["Sha256"]),
        str(raw["SelectedAt"]),
        str(raw["PreviousSha256"]) if raw.get("PreviousSha256") is not None else None,
        int(raw["PreviousVersion"]) if raw.get("PreviousVersion") is not None else None,
    )

def manifest_to_raw(manifest: AIcPackageSelectionManifest) -> dict[str, object]:
    return {
        "FormatVersion": 1,
        "RecordRevision": manifest.record_revision,
        "LastTransactionId": manifest.last_transaction_id,
        "Selections": [_selection_to_raw(item) for item in manifest.selections],
    }

def manifest_from_raw(raw: Mapping[str, object]) -> AIcPackageSelectionManifest:
    format_version = int(raw.get("FormatVersion", 0))
    if format_version != 1:
        raise AIxPersistenceError("active package set requires format_version 1")
    values = raw.get("Selections", ())
    if not isinstance(values, list):
        raise AIxPersistenceError("active package set selections must be an array")
    revision = raw.get("RecordRevision", 0)
    return AIcPackageSelectionManifest(
        int(revision),
        tuple(_selection_from_raw(item) for item in values if isinstance(item, Mapping)),
        str(raw["LastTransactionId"]) if raw.get("LastTransactionId") is not None else None,
    )
