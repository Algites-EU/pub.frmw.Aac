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

from .aic_package_store import AIcPackageStore

_PACKAGE_SELECTION_NAMESPACE = "aac.packages.selection"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class AIcPackageSelectionStore:
    def __init__(
        self, store: AIiStateStore | None = None,
        manifest_store: AIcDurablePackageSelectionManifestStore | None = None,
    ) -> None:
        self.store = store or AIcInMemoryStateStore()
        self.manifest_store = manifest_store
        if self.manifest_store is not None and not self.manifest_store.path.exists():
            self._migrate_legacy_state_if_present()

    @staticmethod
    def _key(application_scope_id: str, component_id: str) -> str:
        return f"{application_scope_id}:{component_id}"

    def _migrate_legacy_state_if_present(self) -> None:
        raw_values = self.store.list(_PACKAGE_SELECTION_NAMESPACE)
        if not raw_values:
            return
        values: list[AIcPackageSelection] = []
        for key, raw in raw_values.items():
            application_scope_id, component_id = key.split(":", 1)
            values.append(AIcPackageSelection(
                application_scope_id, component_id, int(raw["component_version"]), str(raw["sha256"]),
                str(raw["selected_at"]),
                str(raw["previous_sha256"]) if raw.get("previous_sha256") is not None else None,
                int(raw["previous_version"]) if raw.get("previous_version") is not None else None,
            ))
        manifest = AIcPackageSelectionManifest(1, tuple(sorted(values, key=lambda item: (item.application_scope_id, item.component_id))))
        self.manifest_store.write(manifest, expected_record_revision=0)
        records = self.store.list_records(_PACKAGE_SELECTION_NAMESPACE)
        self.store.apply(tuple(
            AIcStateMutation.delete(
                _PACKAGE_SELECTION_NAMESPACE, key, expected_record_revision=records[key].record_revision
            )
            for key in raw_values if key in records
        ))

    def manifest(self) -> AIcPackageSelectionManifest:
        if self.manifest_store is not None:
            return self.manifest_store.read()
        values = []
        for key, raw in self.store.list(_PACKAGE_SELECTION_NAMESPACE).items():
            application_scope_id, component_id = key.split(":", 1)
            values.append(AIcPackageSelection(
                application_scope_id, component_id, int(raw["component_version"]), str(raw["sha256"]),
                str(raw["selected_at"]),
                str(raw["previous_sha256"]) if raw.get("previous_sha256") is not None else None,
                int(raw["previous_version"]) if raw.get("previous_version") is not None else None,
            ))
        return AIcPackageSelectionManifest(0, tuple(sorted(values, key=lambda item: (item.application_scope_id, item.component_id))))

    def _write_manifest(self, manifest: AIcPackageSelectionManifest) -> None:
        if self.manifest_store is not None:
            current = self.manifest_store.read()
            self.manifest_store.write(manifest, expected_record_revision=current.record_revision)
            return
        current_records = self.store.list_records(_PACKAGE_SELECTION_NAMESPACE)
        current_keys = set(current_records)
        target = {self._key(item.application_scope_id, item.component_id): item for item in manifest.selections}
        mutations = []
        for key in current_keys - set(target):
            mutations.append(AIcStateMutation.delete(
                _PACKAGE_SELECTION_NAMESPACE, key,
                expected_record_revision=current_records[key].record_revision,
            ))
        for key, item in target.items():
            current = current_records.get(key)
            mutations.append(AIcStateMutation.put(_PACKAGE_SELECTION_NAMESPACE, key, {
                "component_version": item.component_version,
                "sha256": item.sha256,
                "selected_at": item.selected_at,
                "previous_sha256": item.previous_sha256,
                "previous_version": item.previous_version,
            }, expected_record_revision=None if current is None else current.record_revision, expect_absent=current is None))
        self.store.apply(tuple(mutations))

    def get(self, application_scope_id: str, component_id: str) -> AIcPackageSelection | None:
        return next((
            item for item in self.manifest().selections
            if item.application_scope_id == application_scope_id and item.component_id == component_id
        ), None)

    def all(self) -> tuple[AIcPackageSelection, ...]:
        return self.manifest().selections

    def plan_replacements(
        self, application_scope_id: str, packages: tuple[AIcStoredPackage, ...]
    ) -> tuple[AIcPackageSelectionManifest, AIcPackageSelectionManifest]:
        ids = [item.component_id for item in packages]
        if len(ids) != len(set(ids)):
            raise AIxPackageManagementError("package replacement transaction must be unique by component id")
        for package in packages:
            if package.state is not AInStoredPackageState.INSTALLED:
                raise AIxPackageManagementError("only installed package artifacts can be selected")
        source = self.manifest()
        values = {(item.application_scope_id, item.component_id): item for item in source.selections}
        for package in packages:
            conflicts = tuple(
                item for item in source.selections
                if item.component_id == package.component_id
                and item.application_scope_id != application_scope_id
                and (item.component_version != package.component_version or item.sha256 != package.sha256)
            )
            if conflicts:
                scopes = ", ".join(sorted(item.application_scope_id for item in conflicts))
                raise AIxPackageRevisionConflict(
                    f"component {package.component_id!r} already has a different active artifact in scopes: {scopes}"
                )
            key = (application_scope_id, package.component_id)
            previous = values.get(key)
            values[key] = AIcPackageSelection(
                application_scope_id, package.component_id, package.component_version, package.sha256, _now(),
                None if previous is None else previous.sha256,
                None if previous is None else previous.component_version,
            )
        target = AIcPackageSelectionManifest(
            source.record_revision + 1,
            tuple(sorted(values.values(), key=lambda item: (item.application_scope_id, item.component_id))),
            None,
        )
        return source, target

    def commit_planned(
        self, source: AIcPackageSelectionManifest, target: AIcPackageSelectionManifest,
        *, transaction_id: str | None = None,
    ) -> AIcPackageSelectionManifest:
        current = self.manifest()
        if current.record_revision != source.record_revision or current.selections != source.selections:
            raise AIxPackageRevisionConflict("active package set changed after replacement planning")
        committed = replace(target, last_transaction_id=transaction_id)
        if self.manifest_store is not None:
            self.manifest_store.write(committed, expected_record_revision=source.record_revision)
        else:
            self._write_manifest(committed)
        return committed

    def select(self, application_scope_id: str, package: AIcStoredPackage) -> AIcPackageSelection:
        source, target = self.plan_replacements(application_scope_id, (package,))
        committed = self.commit_planned(source, target)
        return next(
            item for item in committed.selections
            if item.application_scope_id == application_scope_id and item.component_id == package.component_id
        )

    def references(self, package: AIcStoredPackage) -> tuple[AIcPackageSelection, ...]:
        return tuple(
            item for item in self.all()
            if item.component_id == package.component_id
            and item.component_version == package.component_version
            and item.sha256 == package.sha256
        )

    def rollback(self, application_scope_id: str, component_id: str, package_store: AIcPackageStore) -> AIcPackageSelection:
        current = self.get(application_scope_id, component_id)
        if current is None or current.previous_sha256 is None or current.previous_version is None:
            raise AIxPackageRevisionConflict(f"no previous package selection exists for {component_id!r}")
        previous = package_store.find(component_id, current.previous_version, current.previous_sha256)
        if previous is None:
            obsolete = package_store.find(
                component_id, current.previous_version, current.previous_sha256, AInStoredPackageState.OBSOLETE,
            )
            if obsolete is None:
                raise AIxPackageRevisionConflict("previous package artifact is no longer retained")
            previous = package_store.restore_obsolete(obsolete)
        return self.select(application_scope_id, previous)
