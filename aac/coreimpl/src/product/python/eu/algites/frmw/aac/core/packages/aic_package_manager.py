from __future__ import annotations
import hashlib
import json
import os
import shutil
import ssl
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import quote, unquote, urljoin, urlparse
from urllib.request import Request, urlopen
import yaml
from eu.algites.frmw.aac.core.authentication.api import AIcAuthenticationMaterial
from eu.algites.frmw.aac.core.descriptor.api import AIcComponentDescriptor
from eu.algites.frmw.aac.core.errors import AIxPackageDigestMismatch, AIxPackageManagementError, AIxPackageRevisionConflict
from eu.algites.frmw.aac.core.packages.api import (
    AInPackageUpdatePolicy,
    AInStoredPackageState,
    AIcPackageAutomationPolicy,
    AIcPackageCandidate,
    AIcPackageProvenance,
    AIcPackageReconciliationAction,
    AIcPackageReconciliationPlan,
    AIcPackageSelection,
    AIcPackageSelectionManifest,
    AIcPackageSidecar,
    AIcPackageStoreLayout,
    AIcStoredPackage,
    AIcWorkspaceComponentLock,
    AIcWorkspaceComponentLockEntry,
    AIcWorkspaceComponentRequirement,
    AIcWorkspaceComponentRequirements,
    AIiPackageSource,
)
from eu.algites.frmw.aac.core.persistence.api import AIcStateMutation, AIiStateStore
from eu.algites.frmw.aac.core.verification.api import AIcVerificationInput, AIcVerificationOutput, AIiPackageVerifier
from eu.algites.frmw.aac.core.presentation.api import normalize_display_text
from eu.algites.frmw.aac.core.authentication.implementation import AIcAuthenticationService
from eu.algites.frmw.aac.core.descriptor.loader import AIcDescriptorLoader
from eu.algites.frmw.aac.core.persistence.aic_in_memory_state_store import AIcInMemoryStateStore
from eu.algites.frmw.aac.core.packages.transactions import AIcDurablePackageSelectionManifestStore, AIcPackageReplacementJournal
from eu.algites.frmw.aac.core.persistence.durable import atomic_write_json, durable_replace, fsync_directory, fsync_file

from .aic_package_selection_store import AIcPackageSelectionStore
from .aic_package_source_registry import AIcPackageSourceRegistry
from .aic_package_store import AIcPackageStore
from .aic_package_verifier_registry import AIcPackageVerifierRegistry

def _candidate_from_lock(entry: AIcWorkspaceComponentLockEntry) -> AIcPackageCandidate:
    return AIcPackageCandidate(
        component_id=entry.component_id, component_version=entry.component_version, source_id=entry.source_id,
        artifact_uri=entry.artifact_uri, artifact_filename=entry.artifact_filename, expected_sha256=entry.sha256,
        package_format=entry.package_format, descriptor_path=entry.descriptor_path, runtime_package=entry.runtime_package,
        verifier_id=entry.verifier_id, sidecars=entry.sidecars,
    )

class AIcPackageManager:
    def __init__(
        self,
        layout: AIcPackageStoreLayout,
        *,
        authentication: AIcAuthenticationService | None = None,
        store: AIiStateStore | None = None,
        automation_policy: AIcPackageAutomationPolicy = AIcPackageAutomationPolicy(),
    ) -> None:
        self.authentication = authentication or AIcAuthenticationService()
        self.package_store = AIcPackageStore(layout)
        self.sources = AIcPackageSourceRegistry()
        self.verifiers = AIcPackageVerifierRegistry()
        self.state_store = store or AIcInMemoryStateStore()
        state_root = Path(layout.product_root) / layout.core_state_subdirectory
        mutation_lock_path = Path(getattr(
            self.state_store, "mutation_lock_path", state_root / layout.core_lock_filename
        ))
        self.selection_manifest_store = AIcDurablePackageSelectionManifestStore(
            state_root / "active-package-set.json", mutation_lock_path=mutation_lock_path
        )
        self.selections = AIcPackageSelectionStore(self.state_store, self.selection_manifest_store)
        self.transactions = AIcPackageReplacementJournal(
            layout, self.selection_manifest_store, self.state_store
        )
        self.transaction_recovery = self.transactions.recover(self.package_store)
        self.automation_policy = automation_policy

    def register_source(self, source_id: str, source: AIiPackageSource, *, priority: int = 0) -> None:
        self.sources.register(source_id, source, priority=priority)

    def register_verifier(self, verifier_id: str, verifier: AIiPackageVerifier) -> None:
        self.verifiers.register(verifier_id, verifier)

    def _verifier_for(self, candidate: AIcPackageCandidate, fallback: AIiPackageVerifier | None = None) -> AIiPackageVerifier:
        if candidate.verifier_id is not None:
            return self.verifiers.get(candidate.verifier_id)
        if fallback is not None:
            return fallback
        raise AIxPackageManagementError(f"package candidate {candidate.component_id!r} does not select a verifier")

    def download(self, candidate: AIcPackageCandidate, *, fallback_verifier: AIiPackageVerifier | None = None,
                 context: Mapping[str, object] | None = None) -> AIcStoredPackage:
        record = self.package_store.store_downloaded(candidate, authentication=self.authentication, context=context)
        if self.automation_policy.verify_on_download:
            verifier = self._verifier_for(candidate, fallback_verifier)
            output = verifier.verify(AIcVerificationInput(
                candidate.component_id, candidate.component_version, candidate.runtime_package,
                candidate.artifact_uri, candidate.metadata, record.artifact_path,
            ))
            if not output.valid:
                raise AIxPackageManagementError("downloaded package verification failed: " + "; ".join(output.diagnostics))
            provenance = replace(record.provenance, verifier_id=output.verifier_id or candidate.verifier_id,
                                 signer_identity=output.signer_identity, verification_metadata=dict(output.metadata))
            record = replace(record, provenance=provenance)
            self.package_store._write_record(Path(record.artifact_path).parent, record)
        return record

    def install(self, candidate: AIcPackageCandidate, downloaded: AIcStoredPackage, *, fallback_verifier: AIiPackageVerifier | None = None) -> AIcStoredPackage:
        verifier = self._verifier_for(candidate, fallback_verifier)
        return self.package_store.install(downloaded, verifier, verifier_id=candidate.verifier_id)

    def descriptor_from_artifact(self, package: AIcStoredPackage) -> AIcComponentDescriptor:
        if package.package_format.upper() not in {"PYTHON_WHEEL", "ZIP"}:
            raise AIxPackageManagementError(f"descriptor inspection unsupported for package format {package.package_format!r}")
        from zipfile import ZipFile, BadZipFile
        try:
            with ZipFile(package.artifact_path) as archive:
                text = archive.read(package.descriptor_path).decode("utf-8")
        except (OSError, BadZipFile, KeyError, UnicodeDecodeError) as exc:
            raise AIxPackageManagementError(f"cannot inspect component descriptor in package artifact: {exc}") from exc
        descriptor = AIcDescriptorLoader.load_text(text, source=f"{package.artifact_path}!/{package.descriptor_path}")
        if descriptor.id != package.component_id or descriptor.version != package.component_version:
            raise AIxPackageManagementError("package manifest component identity does not match descriptor inside artifact")
        return descriptor

    @staticmethod
    def automatic_entitlement_allows(descriptor: AIcComponentDescriptor, effective_permission_ids: set[tuple[str, int, str]]) -> bool:
        if not descriptor.provided_capability_entitlements:
            return True
        if any(permission.implicit for item in descriptor.provided_capability_entitlements for permission in item.permissions):
            return True
        declared = {
            (item.capability_id, item.capability_version, permission.id)
            for item in descriptor.provided_capability_entitlements for permission in item.permissions
        }
        return bool(declared & effective_permission_ids)

    def mark_obsolete(self, package: AIcStoredPackage) -> AIcStoredPackage:
        references = self.selections.references(package)
        if references:
            scopes = ", ".join(item.application_scope_id for item in references)
            raise AIxPackageManagementError(
                f"cannot mark selected package obsolete; selected by application/workspace scopes: {scopes}"
            )
        return self.package_store.mark_obsolete(package)

    def restore_obsolete(self, package: AIcStoredPackage) -> AIcStoredPackage:
        return self.package_store.restore_obsolete(package)


    def begin_replacement_transaction(
        self, application_scope_id: str, packages: tuple[AIcStoredPackage, ...],
        core_state_snapshot: Mapping[str, Mapping[str, Mapping[str, object]]],
    ):
        source_manifest, target_manifest = self.selections.plan_replacements(application_scope_id, packages)
        return self.transactions.begin(
            application_scope_id, source_manifest, target_manifest, packages, core_state_snapshot
        )

    def mark_replacement_cutover_started(self, transaction) -> None:
        self.transactions.mark_cutover_started(
            transaction.transaction_id, transaction.core_state_snapshot
        )

    def commit_replacement_selections(
        self, transaction
    ) -> tuple[AIcPackageSelectionManifest, tuple[str, ...]]:
        committed = self.selections.commit_planned(
            transaction.source_manifest, transaction.target_manifest, transaction_id=transaction.transaction_id
        )
        diagnostics: list[str] = []
        try:
            self.transactions.mark_target_committed(transaction.transaction_id)
        except Exception as exc:
            # The active package-set manifest is the durable commit marker.  If updating the journal
            # phase fails after that atomic replacement, the transaction is nevertheless committed;
            # startup recovery infers this from record revision + transaction id and completes cleanup.
            diagnostics.append(f"target package set committed; journal phase update deferred: {exc}")
        return committed, tuple(diagnostics)

    def complete_replacement_transaction(
        self, transaction, packages: tuple[AIcStoredPackage, ...]
    ) -> tuple[tuple[AIcStoredPackage, ...], tuple[str, ...]]:
        retired: list[AIcStoredPackage] = []
        diagnostics: list[str] = []
        for package in packages:
            for old in self.package_store.records(AInStoredPackageState.INSTALLED, package.component_id):
                if old.identity == package.identity or self.selections.references(old):
                    continue
                try:
                    retired.append(self.package_store.mark_obsolete(old))
                except Exception as exc:
                    diagnostics.append(
                        f"deferred cleanup for {old.component_id}/{old.component_version}/{old.sha256}: {exc}"
                    )
        if diagnostics:
            # Keep the active-transaction pointer. Startup recovery will deterministically finish
            # the already-committed target cleanup; release the process lock because the durable
            # active-set record is already authoritative.
            self.transactions.release_cutover_lock()
            return tuple(retired), tuple(diagnostics)
        self.transactions.mark_cleanup_completed(transaction.transaction_id)
        self.transactions.finish(transaction.transaction_id)
        return tuple(retired), ()

    def rollback_replacement_transaction(self, transaction, diagnostics: tuple[str, ...] = ()) -> None:
        self.transactions.mark_rolled_back(transaction.transaction_id, diagnostics)
        self.transactions.finish(transaction.transaction_id)

    def release_replacement_cutover_lock(self) -> None:
        self.transactions.release_cutover_lock()

    def activate_replacements(
        self, application_scope_id: str, packages: tuple[AIcStoredPackage, ...]
    ) -> tuple[dict[str, AIcStoredPackage | None], tuple[AIcStoredPackage, ...]]:
        """Atomically select a replacement set and retire unselected old artifacts.

        Core replacement code uses the explicit durable transaction methods above.  This convenience
        method remains for package-only callers and still commits the full selection set atomically.
        """
        previous: dict[str, AIcStoredPackage | None] = {}
        for package in packages:
            selection = self.selections.get(application_scope_id, package.component_id)
            previous[package.component_id] = (
                self.package_store.find(package.component_id, selection.component_version, selection.sha256)
                if selection is not None else None
            )
        source, target = self.selections.plan_replacements(application_scope_id, packages)
        self.selections.commit_planned(source, target)
        retired: list[AIcStoredPackage] = []
        for package in packages:
            for old in self.package_store.records(AInStoredPackageState.INSTALLED, package.component_id):
                if old.identity == package.identity or self.selections.references(old):
                    continue
                retired.append(self.package_store.mark_obsolete(old))
        return previous, tuple(retired)

    def rollback_replacements(
        self, application_scope_id: str, previous: Mapping[str, AIcStoredPackage | None],
        targets: tuple[AIcStoredPackage, ...],
    ) -> None:
        """Legacy in-process compensation helper for package-only callers."""
        restored_targets = []
        for component_id, old in previous.items():
            if old is None:
                continue
            restored = old
            if old.state is AInStoredPackageState.OBSOLETE:
                restored = self.package_store.restore_obsolete(old)
            elif self.package_store.find(old.component_id, old.component_version, old.sha256) is None:
                obsolete = self.package_store.find(
                    old.component_id, old.component_version, old.sha256, AInStoredPackageState.OBSOLETE
                )
                if obsolete is not None:
                    restored = self.package_store.restore_obsolete(obsolete)
            restored_targets.append(restored)
        if restored_targets:
            source, target = self.selections.plan_replacements(application_scope_id, tuple(restored_targets))
            self.selections.commit_planned(source, target)
        for target in targets:
            current = self.package_store.find(target.component_id, target.component_version, target.sha256)
            if current is not None and not self.selections.references(current):
                self.package_store.mark_obsolete(current)

    def plan_workspace(self, requirements: AIcWorkspaceComponentRequirements,
                       lock: AIcWorkspaceComponentLock | None = None) -> AIcPackageReconciliationPlan:
        actions: list[AIcPackageReconciliationAction] = []
        installed = self.package_store.records(AInStoredPackageState.INSTALLED)
        by_component: dict[str, list[AIcStoredPackage]] = {}
        for item in installed:
            by_component.setdefault(item.component_id, []).append(item)
        for requirement in requirements.requirements:
            lock_entry = lock.entry(requirement.component_id) if lock is not None else None
            existing = [item for item in by_component.get(requirement.component_id, ()) if requirement.accepts(item.component_version)]
            if lock_entry is not None:
                exact = next((item for item in existing if item.component_version == lock_entry.component_version and item.sha256 == lock_entry.sha256), None)
                if exact is not None:
                    actions.append(AIcPackageReconciliationAction(requirement.component_id, "SATISFIED", reason="locked artifact is installed"))
                    continue
                candidate = _candidate_from_lock(lock_entry)
            else:
                candidates = self.sources.candidates(requirement)
                candidate = candidates[0] if candidates else None
                if existing and candidate is not None:
                    newest = max(existing, key=lambda item: item.component_version)
                    if newest.component_version >= candidate.component_version:
                        actions.append(AIcPackageReconciliationAction(requirement.component_id, "SATISFIED", reason="compatible installed artifact is current"))
                        continue
                elif existing:
                    actions.append(AIcPackageReconciliationAction(requirement.component_id, "SATISFIED", reason="compatible artifact is installed"))
                    continue
            if candidate is None:
                actions.append(AIcPackageReconciliationAction(
                    requirement.component_id, "MISSING" if requirement.required else "OPTIONAL_MISSING",
                    reason="no compatible package candidate",
                ))
                continue
            if requirements.update_policy is AInPackageUpdatePolicy.MANUAL:
                action = "INSTALL_AVAILABLE"
            elif requirements.update_policy is AInPackageUpdatePolicy.NOTIFY:
                action = "UPDATE_AVAILABLE"
            elif requirements.update_policy is AInPackageUpdatePolicy.AUTO_LOCKED and lock_entry is None:
                action = "LOCK_REQUIRED"
            else:
                action = "AUTO_INSTALL"
            actions.append(AIcPackageReconciliationAction(requirement.component_id, action, candidate, "compatible candidate selected"))
        return AIcPackageReconciliationPlan(requirements.workspace_id, requirements.update_policy, tuple(actions))
