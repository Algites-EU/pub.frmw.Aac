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

@dataclass(frozen=True, slots=True)
class AIcPackageReplacementJournalHandle:
    transaction_id: str
    application_scope_id: str
    source_manifest: AIcPackageSelectionManifest
    target_manifest: AIcPackageSelectionManifest
    target_packages: tuple[tuple[str, int, str], ...]
    core_state_snapshot: object
