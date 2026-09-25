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
