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

from algites.lib.aac.coreintf.configuration import (
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
from algites.lib.aac.coreintf.context import AIcConfigurationScope
from algites.lib.aac.coreintf.persistence import AInPersistenceCapability, AInRecordRevisionKind

from .authentication import AIcAuthenticationService
from .durable import AIcInterProcessFileLock, atomic_write_text
from .errors import AIxAuthenticationError, AIxConfigurationRevisionConflict


class AIcConfigurationDocumentCodec:
    FORMAT_VERSION = 1

    @staticmethod
    def encode_snapshot(snapshot: AIcConfigurationProviderSnapshot) -> dict[str, object]:
        payload = snapshot.payload
        return {
            "format_version": 1,
            "configuration_scope": {"type": snapshot.configuration_scope.type, "id": snapshot.configuration_scope.id},
            "configuration_target": _encode_target(snapshot.configuration_target),
            "record_revision": snapshot.record_revision,
            "payload": {
                "configuration_schema_id": payload.configuration_schema_id,
                "configuration_schema_version": payload.configuration_schema_version,
                "written_by_component_version": payload.written_by_component_version,
                "values": copy.deepcopy(dict(payload.values)),
                "policies": {
                    key: [{"mode": item.mode.value, "value": copy.deepcopy(item.value)} for item in values]
                    for key, values in payload.policies.items()
                },
                "metadata": copy.deepcopy(dict(payload.metadata)),
            },
        }

    @staticmethod
    def decode_snapshot(raw: Mapping[str, object]) -> AIcConfigurationProviderSnapshot:
        format_version = int(raw.get("format_version", 0))
        if format_version != 1:
            raise ValueError("unsupported configuration provider document format_version; expected 1")
        raw_scope = _mapping(raw.get("configuration_scope"), "configuration_scope")
        raw_target = _mapping(raw.get("configuration_target"), "configuration_target")
        raw_payload = _mapping(raw.get("payload"), "payload")
        scope = AIcConfigurationScope(str(raw_scope["type"]), _optional_str(raw_scope.get("id")))
        target = _decode_target(raw_target)
        policies = {}
        for property_id, raw_items in _mapping(raw_payload.get("policies", {}), "payload.policies").items():
            if not isinstance(raw_items, list):
                raise ValueError("policy list must be an array")
            policies[str(property_id)] = tuple(
                AIcConfigurationPolicy(AInConfigurationPolicyMode(str(_mapping(item, "policy")["mode"])), _mapping(item, "policy").get("value"))
                for item in raw_items
            )
        payload = AIcConfigurationPersistedPayload(
            configuration_target=target,
            configuration_schema_id=str(raw_payload["configuration_schema_id"]),
            configuration_schema_version=int(raw_payload["configuration_schema_version"]),
            written_by_component_version=int(raw_payload["written_by_component_version"]),
            values=dict(_mapping(raw_payload.get("values", {}), "payload.values")),
            policies=policies,
            metadata=dict(_mapping(raw_payload.get("metadata", {}), "payload.metadata")),
        )
        revision = raw.get("record_revision")
        return AIcConfigurationProviderSnapshot(scope, target, revision, payload)

    @staticmethod
    def encode_change_set(change_set: AIcConfigurationChangeSet) -> dict[str, object]:
        return {
            "configuration_scope": {"type": change_set.configuration_scope.type, "id": change_set.configuration_scope.id},
            "configuration_provider_id": change_set.configuration_provider_id,
            "configuration_target": _encode_target(change_set.configuration_target),
            "expected_record_revision": change_set.expected_record_revision,
            "configuration_schema_id": change_set.configuration_schema_id,
            "configuration_schema_version": change_set.configuration_schema_version,
            "written_by_component_version": change_set.written_by_component_version,
            "changes": [
                {
                    "property_id": change.property_id,
                    "operation": change.operation.value,
                    **({"value": copy.deepcopy(change.value)} if change.has_value else {}),
                    **({"policy_modes": [
                        {"mode": item.mode.value, "value": copy.deepcopy(item.value)} for item in change.policy_modes
                    ]} if change.policy_modes else {}),
                }
                for change in change_set.changes
            ],
        }

    @staticmethod
    def contributions(snapshot: AIcConfigurationProviderSnapshot) -> tuple[AIcConfigurationContribution, ...]:
        payload = snapshot.payload
        keys = list(dict.fromkeys([*payload.values.keys(), *payload.policies.keys()]))
        result = []
        for property_id in keys:
            has_value = property_id in payload.values
            result.append(AIcConfigurationContribution(
                property_id=str(property_id),
                value=payload.values.get(property_id),
                has_value=has_value,
                policy_modes=tuple(payload.policies.get(property_id, ())),
                configuration_schema_id=payload.configuration_schema_id,
                configuration_schema_version=payload.configuration_schema_version,
                written_by_component_version=payload.written_by_component_version,
                metadata={"provider_record_revision": snapshot.record_revision},
            ))
        return tuple(result)


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


class AIcHttpConfigurationProvider(AIiConfigurationProvider):
    """Reference HTTP provider using GET plus PATCH change-set or PUT full-document semantics."""

    @property
    def revision_kind(self) -> AInRecordRevisionKind:
        return AInRecordRevisionKind.OPAQUE_STRING

    def persistence_capabilities(self, request: AIcConfigurationProviderRequest) -> tuple[AInPersistenceCapability, ...]:
        result = [AInPersistenceCapability.READ]
        if not self.read_only:
            result.append(AInPersistenceCapability.SINGLE_RECORD_CAS)
        return tuple(result)

    def __init__(
        self,
        base_url: str,
        *,
        authentication: AIcAuthenticationService | None = None,
        authentication_profile_id: str | None = None,
        read_only: bool = False,
        allow_policy_write: bool = True,
        timeout_seconds: float = 10.0,
        mutation_method: str = "PATCH",
    ) -> None:
        if not base_url:
            raise ValueError("HTTP configuration-provider base_url must not be empty")
        self.base_url = base_url
        self.authentication = authentication
        self.authentication_profile_id = authentication_profile_id
        self.read_only = read_only
        self.allow_policy_write = allow_policy_write
        self.timeout_seconds = float(timeout_seconds)
        self.mutation_method = mutation_method.upper()
        if self.mutation_method not in {"PATCH", "PUT"}:
            raise ValueError("HTTP mutation_method must be PATCH or PUT")

    def _url(self, request: AIcConfigurationProviderRequest) -> str:
        query = urlencode({
            "configuration_scope_type": request.configuration_scope.type,
            "configuration_scope_id": request.configuration_scope.id or "",
            "target_kind": request.configuration_target.kind.value,
            "component_id": request.configuration_target.component_id,
            "provider_instance_id": request.configuration_target.provider_instance_id or "",
        })
        return self.base_url + ("&" if "?" in self.base_url else "?") + query

    def snapshot(self, request: AIcConfigurationProviderRequest) -> AIcConfigurationProviderSnapshot | None:
        status, headers, body = self._request("GET", self._url(request), request.context)
        if status == 404:
            return None
        raw = json.loads(body.decode("utf-8"))
        snapshot = AIcConfigurationDocumentCodec.decode_snapshot(raw)
        _assert_snapshot_identity(snapshot, request)
        etag = headers.get("ETag")
        if etag is not None:
            snapshot = AIcConfigurationProviderSnapshot(snapshot.configuration_scope, snapshot.configuration_target, _strip_etag(etag), snapshot.payload)
        return snapshot

    def contributions(self, request: AIcConfigurationProviderRequest):
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
        request = AIcConfigurationProviderRequest(change_set.configuration_target, change_set.configuration_scope, change_set.actor_context)
        if self.mutation_method == "PATCH":
            body = json.dumps({"configuration_change_set": AIcConfigurationDocumentCodec.encode_change_set(change_set)}).encode("utf-8")
            status, headers, response = self._request(
                "PATCH", self._url(request), request.context, body=body, expected_record_revision=change_set.expected_record_revision
            )
            revision = _response_revision(headers, response)
            return AIcConfigurationMutationResult(revision, tuple(dict.fromkeys(c.property_id for c in change_set.changes)))
        current = self.snapshot(request)
        actual = None if current is None else current.record_revision
        _check_revision(change_set.expected_record_revision, actual)
        if current is None:
            if not all((change_set.configuration_schema_id, change_set.configuration_schema_version, change_set.written_by_component_version)):
                raise ValueError("creating configuration requires schema id/version and written_by_component_version")
            payload = AIcConfigurationPersistedPayload(
                change_set.configuration_target, str(change_set.configuration_schema_id), int(change_set.configuration_schema_version),
                int(change_set.written_by_component_version),
            )
        else:
            payload = current.payload
        updated = _apply_change_set_to_payload(payload, change_set)
        return self.replace_payload(request, updated, actual)

    def replace_payload(self, request, payload, expected_record_revision=None):
        if self.read_only:
            raise PermissionError("configuration-provider is read-only")
        snapshot = AIcConfigurationProviderSnapshot(request.configuration_scope, request.configuration_target, expected_record_revision, payload)
        body = json.dumps(AIcConfigurationDocumentCodec.encode_snapshot(snapshot)).encode("utf-8")
        status, headers, response = self._request(
            "PUT", self._url(request), request.context, body=body, expected_record_revision=expected_record_revision
        )
        return AIcConfigurationMutationResult(_response_revision(headers, response), tuple(dict.fromkeys([*payload.values.keys(), *payload.policies.keys()])))

    def _request(self, method, url, context, *, body=None, expected_record_revision=None):
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if expected_record_revision is not None:
            headers["If-Match"] = _etag(expected_record_revision)
        material = self.authentication.material(
            self.authentication_profile_id, transport_kind="HTTP", endpoint=url, context=context
        ) if self.authentication is not None else None
        if material is not None:
            headers.update(material.headers)
        ssl_context = None
        if material is not None and material.client_certificate is not None:
            ssl_context = ssl.create_default_context()
            certificate = material.client_certificate
            ssl_context.load_cert_chain(
                certificate.certificate_path, certificate.private_key_path, certificate.private_key_password
            )
        request = Request(url, data=body, method=method, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout_seconds, context=ssl_context) as response:
                return response.status, response.headers, response.read()
        except HTTPError as exc:
            if exc.code == 404 and method == "GET":
                return 404, exc.headers, b""
            if exc.code in {409, 412}:
                actual = _strip_etag(exc.headers.get("ETag")) if exc.headers.get("ETag") else None
                raise AIxConfigurationRevisionConflict(expected_record_revision, actual) from exc
            if exc.code in {401, 403}:
                raise AIxAuthenticationError(f"HTTP configuration-provider authentication/authorization failed: {exc.code}") from exc
            raise
        except URLError as exc:
            raise ConnectionError(f"HTTP configuration-provider request failed: {exc}") from exc


def _mapping(value, label):
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _optional_str(value):
    return None if value is None else str(value)


def _encode_target(target):
    result = {"kind": target.kind.value, "component_id": target.component_id}
    if target.provider_instance_id is not None:
        result["provider_instance_id"] = target.provider_instance_id
    return result


def _decode_target(raw):
    return AIcConfigurationTarget(
        AInConfigurationTargetKind(str(raw["kind"])), str(raw["component_id"]), _optional_str(raw.get("provider_instance_id"))
    )


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


def _etag(value) -> str:
    text = str(value)
    return text if text.startswith('"') else f'"{text}"'


def _strip_etag(value: str):
    text = value.strip()
    if text.startswith('W/'):
        text = text[2:]
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1]
    try:
        return int(text)
    except ValueError:
        return text


def _response_revision(headers, body):
    if headers.get("ETag"):
        return _strip_etag(headers.get("ETag"))
    if body:
        try:
            raw = json.loads(body.decode("utf-8"))
            if isinstance(raw, Mapping):
                if "record_revision" in raw:
                    return raw["record_revision"]
                if "revision" in raw:
                    return raw["revision"]
        except Exception:
            pass
    return None
