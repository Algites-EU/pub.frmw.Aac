from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from algites.lib.aac.coreintf.packages import (
    AIcPackageSelection,
    AIcPackageSelectionManifest,
    AIcPackageStoreLayout,
    AIcPackageTransactionRecovery,
    AIcStoredPackage,
)
from algites.lib.aac.coreintf.persistence import (
    AIcPersistenceTransactionRead,
    AIcPersistenceTransactionWrite,
    AInPersistenceTransactionPhase,
    AIiStateStore,
)

from .durable import AIcInterProcessFileLock, atomic_write_json
from .errors import AIxPersistenceError, AIxPersistenceRevisionConflict
from .persistence import state_snapshot_from_raw, state_snapshot_to_raw
from .transactions import AIcDurableTransactionJournal


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


@dataclass(frozen=True, slots=True)
class AIcPackageReplacementJournalHandle:
    transaction_id: str
    application_scope_id: str
    source_manifest: AIcPackageSelectionManifest
    target_manifest: AIcPackageSelectionManifest
    target_packages: tuple[tuple[str, int, str], ...]
    core_state_snapshot: object


class AIcPackageReplacementJournal:
    """Package-replacement binding of the generic durable persistence transaction journal."""

    _SOURCE_CORE_STATE = "source-core-state.json"

    def __init__(
        self,
        layout: AIcPackageStoreLayout,
        selection_manifest_store: AIcDurablePackageSelectionManifestStore,
        core_state_store: AIiStateStore,
    ) -> None:
        self.layout = layout
        self.state_root = Path(layout.product_root) / layout.core_state_subdirectory
        self.selection_manifest_store = selection_manifest_store
        self.core_state_store = core_state_store
        self.journal = AIcDurableTransactionJournal(
            self.state_root, layout.transactions_subdirectory,
            mutation_lock_path=selection_manifest_store.mutation_lock_path,
        )
        self._cutover_lock: AIcInterProcessFileLock | None = None

    @property
    def transactions_root(self) -> Path:
        return self.journal.transactions_root

    @property
    def active_pointer(self) -> Path:
        return self.journal.active_pointer

    def active_transaction_id(self) -> str | None:
        return self.journal.active_transaction_id()

    def begin(
        self,
        application_scope_id: str,
        source_manifest: AIcPackageSelectionManifest,
        target_manifest: AIcPackageSelectionManifest,
        packages: tuple[AIcStoredPackage, ...],
        core_state_snapshot,
    ) -> AIcPackageReplacementJournalHandle:
        target_packages = tuple((item.component_id, item.component_version, item.sha256) for item in packages)

        def validate() -> None:
            current = self.selection_manifest_store._read_unlocked()
            if current.record_revision != source_manifest.record_revision or current.selections != source_manifest.selections:
                raise AIxPersistenceRevisionConflict(
                    "aac.packages.active-set", source_manifest.record_revision, current.record_revision
                )

        descriptor = self.journal.begin(
            "COMPONENT_REPLACEMENT",
            read_set=(AIcPersistenceTransactionRead(
                "aac.packages.active-set", source_manifest.record_revision
            ),),
            write_set=(AIcPersistenceTransactionWrite(
                "aac.packages.active-set", "REPLACE", target_manifest.record_revision
            ),),
            metadata={
                "application_scope_id": application_scope_id,
                "source_package_set": manifest_to_raw(source_manifest),
                "target_package_set": manifest_to_raw(target_manifest),
                "target_packages": [
                    {"component_id": cid, "component_version": version, "sha256": digest}
                    for cid, version, digest in target_packages
                ],
            },
            recovery_payloads={self._SOURCE_CORE_STATE: state_snapshot_to_raw(core_state_snapshot)},
            validate_under_lock=validate,
        )
        return AIcPackageReplacementJournalHandle(
            descriptor.transaction_id,
            application_scope_id,
            source_manifest,
            target_manifest,
            target_packages,
            core_state_snapshot,
        )

    def mark_cutover_started(self, transaction_id: str, source_snapshot=None) -> None:
        if self._cutover_lock is not None:
            raise AIxPersistenceError("package replacement cutover lock is already held")
        lock = AIcInterProcessFileLock(self.journal.mutation_lock_path)
        lock.__enter__()
        try:
            if source_snapshot is not None and self.core_state_store.snapshot() != source_snapshot:
                raise AIxPersistenceRevisionConflict("aac.core-state", "source snapshot", "changed")
            self.journal.write_phase(transaction_id, AInPersistenceTransactionPhase.COMMIT_STARTED)
            self._cutover_lock = lock
        except Exception:
            lock.__exit__(None, None, None)
            raise

    def release_cutover_lock(self) -> None:
        if self._cutover_lock is not None:
            lock = self._cutover_lock
            self._cutover_lock = None
            lock.__exit__(None, None, None)

    def mark_target_committed(self, transaction_id: str) -> None:
        self.journal.write_phase(transaction_id, AInPersistenceTransactionPhase.COMMITTED)

    def mark_rolled_back(self, transaction_id: str, diagnostics: tuple[str, ...] = ()) -> None:
        self.journal.write_phase(transaction_id, AInPersistenceTransactionPhase.ABORTED, diagnostics)

    def mark_cleanup_completed(self, transaction_id: str, diagnostics: tuple[str, ...] = ()) -> None:
        self.journal.write_phase(transaction_id, AInPersistenceTransactionPhase.CLEANUP_COMPLETED, diagnostics)

    def finish(self, transaction_id: str) -> None:
        try:
            self.journal.remove_recovery_payload(transaction_id, self._SOURCE_CORE_STATE)
            self.journal.finish(transaction_id)
        finally:
            self.release_cutover_lock()

    def recover(self, package_store) -> AIcPackageTransactionRecovery | None:
        with AIcInterProcessFileLock(self.journal.mutation_lock_path):
            return self._recover_locked(package_store)

    def _recover_locked(self, package_store) -> AIcPackageTransactionRecovery | None:
        transaction_id = self.active_transaction_id()
        if transaction_id is None:
            return None
        plan = self.journal.read_plan(transaction_id)
        recorded_phase = self.journal.read_phase(transaction_id)
        metadata = plan.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise AIxPersistenceError(f"transaction {transaction_id} metadata is invalid")
        source_raw = metadata.get("source_package_set")
        target_raw = metadata.get("target_package_set")
        if not isinstance(source_raw, Mapping) or not isinstance(target_raw, Mapping):
            raise AIxPersistenceError(f"transaction {transaction_id} has invalid package-set snapshots")
        source_manifest = manifest_from_raw(source_raw)
        target_manifest = manifest_from_raw(target_raw)
        active_manifest = self.selection_manifest_store.read()

        if recorded_phase in {AInPersistenceTransactionPhase.CLEANUP_COMPLETED, AInPersistenceTransactionPhase.ABORTED}:
            self.finish(transaction_id)
            return AIcPackageTransactionRecovery(
                transaction_id, recorded_phase, "CLEARED_TERMINAL_TRANSACTION_POINTER", ()
            )

        target_committed = (
            active_manifest.last_transaction_id == transaction_id
            and active_manifest.record_revision == target_manifest.record_revision
            and active_manifest.selections == target_manifest.selections
        )
        if target_committed:
            target_keys = {
                (item.component_id, item.component_version, item.sha256)
                for item in target_manifest.selections
            }
            source_component_ids = {item.component_id for item in source_manifest.selections}
            for component_id in source_component_ids:
                for old in package_store.records(component_id=component_id):
                    key = (old.component_id, old.component_version, old.sha256)
                    if old.state.value == "INSTALLED" and key not in target_keys:
                        if not any(
                            item.component_id == old.component_id
                            and item.component_version == old.component_version
                            and item.sha256 == old.sha256
                            for item in target_manifest.selections
                        ):
                            package_store.mark_obsolete(old)
            self.mark_cleanup_completed(transaction_id, ("recovered committed target package set",))
            self.finish(transaction_id)
            return AIcPackageTransactionRecovery(
                transaction_id,
                AInPersistenceTransactionPhase.COMMITTED,
                "COMPLETED_TARGET_CLEANUP",
                (f"recovered transaction recorded as {recorded_phase.value}",),
            )

        current = active_manifest
        if current != source_manifest:
            if current.record_revision != source_manifest.record_revision or current.selections != source_manifest.selections:
                raise AIxPersistenceError(
                    f"cannot recover transaction {transaction_id}: active package set is neither source nor committed target"
                )
        source_state = state_snapshot_from_raw(
            self.journal.read_recovery_payload(transaction_id, self._SOURCE_CORE_STATE)
        )
        self.core_state_store.restore(source_state)
        self.mark_rolled_back(transaction_id, ("recovered source Core/package state after interrupted cutover",))
        self.finish(transaction_id)
        return AIcPackageTransactionRecovery(
            transaction_id,
            AInPersistenceTransactionPhase.ABORTED,
            "RESTORED_SOURCE_STATE",
            (f"recovered transaction recorded as {recorded_phase.value}",),
        )
