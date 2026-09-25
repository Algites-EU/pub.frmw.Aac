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
from .aic_file_system_configuration_provider import AIcFileSystemConfigurationProvider
from .aic_http_configuration_provider import AIcHttpConfigurationProvider

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
