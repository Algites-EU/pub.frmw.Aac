from __future__ import annotations
import copy
import json
import os
import ssl
import tempfile
from pathlib import Path
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from eu.algites.frmw.aac.core.configuration.api import (
    AInConfigurationMutationOperation,
    AInConfigurationPolicyMode,
    AInConfigurationProviderCapability,
    AInConfigurationTargetKind,
    AIcConfigurationChangeSet,
    AIcConfigurationContribution,
    AIcConfigurationMutationResult,
    AIcConfigurationPersistedPayload,
    AIcConfigurationPolicy,
    AIcConfigurationProviderRequest,
    AIcConfigurationProviderSnapshot,
    AIcConfigurationTarget,
    AIiConfigurationProvider,
)
from eu.algites.frmw.aac.core.context.api import AIcConfigurationScope
from eu.algites.frmw.aac.core.persistence.api import AInPersistenceCapability, AInRecordRevisionKind
from eu.algites.frmw.aac.core.authentication.implementation import AIcAuthenticationService
from eu.algites.frmw.aac.core.persistence.durable import AIcInterProcessFileLock, atomic_write_text
from eu.algites.frmw.aac.core.implementation.errors import AIxAuthenticationError, AIxConfigurationRevisionConflict

from .aic_configuration_document_codec import AIcConfigurationDocumentCodec

def _safe_segment(value: str) -> str:
    import urllib.parse
    return urllib.parse.quote(value, safe="")

def _assert_snapshot_identity(snapshot, request):
    if snapshot.configuration_scope != request.configuration_scope or snapshot.configuration_target != request.configuration_target:
        raise ValueError("configuration provider returned a document for a different scope/target")

def _check_revision(expected, actual):
    if expected is not None and str(expected) != str(actual):
        raise AIxConfigurationRevisionConflict(expected, actual)

def _numeric_revision(value):
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        # Filesystem provider owns its format and normally stores numeric revisions.
        raise ValueError(f"filesystem configuration revision {value!r} is not numeric")

def _apply_change_set_to_payload(payload, change_set):
    if payload.configuration_target != change_set.configuration_target:
        raise ValueError("change-set target does not match persisted payload target")
    values = copy.deepcopy(dict(payload.values))
    policies = {key: tuple(items) for key, items in payload.policies.items()}
    for change in change_set.changes:
        if change.operation is AInConfigurationMutationOperation.SET_VALUE:
            values[change.property_id] = copy.deepcopy(change.value)
        elif change.operation is AInConfigurationMutationOperation.DELETE_VALUE:
            values.pop(change.property_id, None)
        elif change.operation is AInConfigurationMutationOperation.SET_POLICY:
            policies[change.property_id] = tuple(change.policy_modes)
        elif change.operation is AInConfigurationMutationOperation.DELETE_POLICY:
            policies.pop(change.property_id, None)
    return AIcConfigurationPersistedPayload(
        payload.configuration_target,
        change_set.configuration_schema_id or payload.configuration_schema_id,
        change_set.configuration_schema_version or payload.configuration_schema_version,
        change_set.written_by_component_version or payload.written_by_component_version,
        values,
        policies,
        dict(payload.metadata),
    )

class AIcFileSystemConfigurationProvider(AIiConfigurationProvider):
    @property
    def revision_kind(self) -> AInRecordRevisionKind:
        return AInRecordRevisionKind.MONOTONIC_INTEGER

    def persistence_capabilities(self, request: AIcConfigurationProviderRequest) -> tuple[AInPersistenceCapability, ...]:
        result = [AInPersistenceCapability.READ]
        if not self.read_only:
            result.append(AInPersistenceCapability.SINGLE_RECORD_CAS)
        return tuple(result)

    def __init__(self, root: str | Path, *, read_only: bool = False, allow_policy_write: bool = True) -> None:
        self.root = Path(root)
        self.read_only = read_only
        self.allow_policy_write = allow_policy_write
        self.mutation_lock_path = self.root / ".aac-configuration.lock"

    def _path(self, request: AIcConfigurationProviderRequest) -> Path:
        scope_type = _safe_segment(request.configuration_scope.type)
        scope_id = _safe_segment(request.configuration_scope.id or "_default")
        component_id = _safe_segment(request.configuration_target.component_id)
        if request.configuration_target.kind is AInConfigurationTargetKind.COMPONENT:
            target = "component"
        else:
            target = "provider-instance-" + _safe_segment(str(request.configuration_target.provider_instance_id))
        return self.root / scope_type / scope_id / component_id / f"{target}.json"

    def snapshot(self, request: AIcConfigurationProviderRequest) -> AIcConfigurationProviderSnapshot | None:
        path = self._path(request)
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        snapshot = AIcConfigurationDocumentCodec.decode_snapshot(raw)
        _assert_snapshot_identity(snapshot, request)
        return snapshot

    def contributions(self, request: AIcConfigurationProviderRequest) -> tuple[AIcConfigurationContribution, ...]:
        snapshot = self.snapshot(request)
        return () if snapshot is None else AIcConfigurationDocumentCodec.contributions(snapshot)

    def capabilities(self, request: AIcConfigurationProviderRequest):
        result = [AInConfigurationProviderCapability.READ]
        if not self.read_only:
            result += [
                AInConfigurationProviderCapability.WRITE_VALUE,
                AInConfigurationProviderCapability.DELETE_VALUE,
                AInConfigurationProviderCapability.ATOMIC_CHANGE_SET,
            ]
            if self.allow_policy_write:
                result += [AInConfigurationProviderCapability.WRITE_POLICY, AInConfigurationProviderCapability.DELETE_POLICY]
        return tuple(result)

    def apply_changes(self, change_set: AIcConfigurationChangeSet) -> AIcConfigurationMutationResult:
        if self.read_only:
            raise PermissionError("configuration-provider is read-only")
        request = AIcConfigurationProviderRequest(
            change_set.configuration_target, change_set.configuration_scope, change_set.actor_context
        )
        current = self.snapshot(request)
        if current is None:
            if change_set.expected_record_revision is not None:
                raise AIxConfigurationRevisionConflict(change_set.expected_record_revision, None)
            if not all((change_set.configuration_schema_id, change_set.configuration_schema_version, change_set.written_by_component_version)):
                raise ValueError("creating configuration requires schema id/version and written_by_component_version")
            payload = AIcConfigurationPersistedPayload(
                change_set.configuration_target,
                str(change_set.configuration_schema_id),
                int(change_set.configuration_schema_version),
                int(change_set.written_by_component_version),
            )
            revision = 0
        else:
            _check_revision(change_set.expected_record_revision, current.record_revision)
            payload = current.payload
            revision = _numeric_revision(current.record_revision)
        updated = _apply_change_set_to_payload(payload, change_set)
        next_revision = revision + 1
        self._write_snapshot(
            AIcConfigurationProviderSnapshot(
                change_set.configuration_scope, change_set.configuration_target, next_revision, updated
            ),
            expected_record_revision=None if current is None else current.record_revision,
            expect_absent=current is None,
        )
        return AIcConfigurationMutationResult(next_revision, tuple(dict.fromkeys(c.property_id for c in change_set.changes)))

    def replace_payload(self, request, payload, expected_record_revision=None):
        if self.read_only:
            raise PermissionError("configuration-provider is read-only")
        current = self.snapshot(request)
        actual = None if current is None else current.record_revision
        _check_revision(expected_record_revision, actual)
        next_revision = _numeric_revision(actual) + 1
        self._write_snapshot(
            AIcConfigurationProviderSnapshot(request.configuration_scope, request.configuration_target, next_revision, payload),
            expected_record_revision=expected_record_revision,
            expect_absent=current is None,
        )
        return AIcConfigurationMutationResult(next_revision, tuple(dict.fromkeys([*payload.values.keys(), *payload.policies.keys()])))

    def _write_snapshot(
        self, snapshot: AIcConfigurationProviderSnapshot, *, expected_record_revision: int | str | None = None,
        expect_absent: bool = False,
    ) -> None:
        path = self._path(AIcConfigurationProviderRequest(snapshot.configuration_target, snapshot.configuration_scope))
        with AIcInterProcessFileLock(self.mutation_lock_path):
            current = None
            if path.exists():
                raw = json.loads(path.read_text(encoding="utf-8"))
                current = AIcConfigurationDocumentCodec.decode_snapshot(raw)
            actual = None if current is None else current.record_revision
            if expect_absent:
                if current is not None:
                    raise AIxConfigurationRevisionConflict(None, actual)
            elif current is not None:
                if expected_record_revision is None or str(expected_record_revision) != str(actual):
                    raise AIxConfigurationRevisionConflict(expected_record_revision, actual)
            elif expected_record_revision is not None:
                raise AIxConfigurationRevisionConflict(expected_record_revision, None)
            data = json.dumps(
                AIcConfigurationDocumentCodec.encode_snapshot(snapshot), indent=2, sort_keys=True, ensure_ascii=False
            ) + "\n"
            atomic_write_text(path, data)
