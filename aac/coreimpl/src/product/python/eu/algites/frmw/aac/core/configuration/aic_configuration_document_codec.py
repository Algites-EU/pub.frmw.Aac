from __future__ import annotations

from eu.algites.frmw.aac.core.configuration.aiig_configuration_provider_document_1 import AIigConfigurationProviderDocument_1
from eu.algites.frmw.aac.core.configuration.aiig_configuration_provider_document_configuration_scope_1 import AIigConfigurationProviderDocumentConfigurationScope_1
from eu.algites.frmw.aac.core.configuration.aiig_configuration_provider_document_payload_1 import AIigConfigurationProviderDocumentPayload_1
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
    result = {"Kind": target.kind.value, "ComponentId": target.component_id}
    if target.provider_instance_id is not None:
        result["ProviderInstanceId"] = target.provider_instance_id
    return result

def _decode_target(raw):
    return AIcConfigurationTarget(
        AInConfigurationTargetKind(str(raw["Kind"])), str(raw["ComponentId"]), _optional_str(raw.get("ProviderInstanceId"))
    )

class AIcConfigurationDocumentCodec:
    FORMAT_VERSION = 1

    @staticmethod
    def encode_snapshot(snapshot: AIcConfigurationProviderSnapshot) -> dict[str, object]:
        payload = snapshot.payload
        return {
            AIigConfigurationProviderDocument_1.SCHEMA_FIELD_NAME__FORMAT_VERSION: 1,
            AIigConfigurationProviderDocument_1.SCHEMA_FIELD_NAME__CONFIGURATION_SCOPE: {AIigConfigurationProviderDocumentConfigurationScope_1.SCHEMA_FIELD_NAME__TYPE: snapshot.configuration_scope.type, AIigConfigurationProviderDocumentConfigurationScope_1.SCHEMA_FIELD_NAME__ID: snapshot.configuration_scope.id},
            AIigConfigurationProviderDocument_1.SCHEMA_FIELD_NAME__CONFIGURATION_TARGET: _encode_target(snapshot.configuration_target),
            AIigConfigurationProviderDocument_1.SCHEMA_FIELD_NAME__RECORD_REVISION: snapshot.record_revision,
            AIigConfigurationProviderDocument_1.SCHEMA_FIELD_NAME__PAYLOAD: {
                AIigConfigurationProviderDocumentPayload_1.SCHEMA_FIELD_NAME__CONFIGURATION_SCHEMA_ID: payload.configuration_schema_id,
                AIigConfigurationProviderDocumentPayload_1.SCHEMA_FIELD_NAME__CONFIGURATION_SCHEMA_VERSION: payload.configuration_schema_version,
                AIigConfigurationProviderDocumentPayload_1.SCHEMA_FIELD_NAME__WRITTEN_BY_COMPONENT_VERSION: payload.written_by_component_version,
                AIigConfigurationProviderDocumentPayload_1.SCHEMA_FIELD_NAME__VALUES: copy.deepcopy(dict(payload.values)),
                AIigConfigurationProviderDocumentPayload_1.SCHEMA_FIELD_NAME__POLICIES: {
                    key: [{"Mode": item.mode.value, "Value": copy.deepcopy(item.value)} for item in values]
                    for key, values in payload.policies.items()
                },
                AIigConfigurationProviderDocumentPayload_1.SCHEMA_FIELD_NAME__METADATA: copy.deepcopy(dict(payload.metadata)),
            },
        }

    @staticmethod
    def decode_snapshot(raw: Mapping[str, object]) -> AIcConfigurationProviderSnapshot:
        format_version = int(raw.get(AIigConfigurationProviderDocument_1.SCHEMA_FIELD_NAME__FORMAT_VERSION, 0))
        if format_version != 1:
            raise ValueError("unsupported configuration provider document format_version; expected 1")
        raw_scope = _mapping(raw.get(AIigConfigurationProviderDocument_1.SCHEMA_FIELD_NAME__CONFIGURATION_SCOPE), "configuration_scope")
        raw_target = _mapping(raw.get(AIigConfigurationProviderDocument_1.SCHEMA_FIELD_NAME__CONFIGURATION_TARGET), "configuration_target")
        raw_payload = _mapping(raw.get(AIigConfigurationProviderDocument_1.SCHEMA_FIELD_NAME__PAYLOAD), "payload")
        scope = AIcConfigurationScope(str(raw_scope[AIigConfigurationProviderDocumentConfigurationScope_1.SCHEMA_FIELD_NAME__TYPE]), _optional_str(raw_scope.get(AIigConfigurationProviderDocumentConfigurationScope_1.SCHEMA_FIELD_NAME__ID)))
        target = _decode_target(raw_target)
        policies = {}
        for property_id, raw_items in _mapping(raw_payload.get(AIigConfigurationProviderDocumentPayload_1.SCHEMA_FIELD_NAME__POLICIES, {}), "payload.policies").items():
            if not isinstance(raw_items, list):
                raise ValueError("policy list must be an array")
            policies[str(property_id)] = tuple(
                AIcConfigurationPolicy(AInConfigurationPolicyMode(str(_mapping(item, "policy")["Mode"])), _mapping(item, "policy").get("Value"))
                for item in raw_items
            )
        payload = AIcConfigurationPersistedPayload(
            configuration_target=target,
            configuration_schema_id=str(raw_payload[AIigConfigurationProviderDocumentPayload_1.SCHEMA_FIELD_NAME__CONFIGURATION_SCHEMA_ID]),
            configuration_schema_version=int(raw_payload[AIigConfigurationProviderDocumentPayload_1.SCHEMA_FIELD_NAME__CONFIGURATION_SCHEMA_VERSION]),
            written_by_component_version=int(raw_payload[AIigConfigurationProviderDocumentPayload_1.SCHEMA_FIELD_NAME__WRITTEN_BY_COMPONENT_VERSION]),
            values=dict(_mapping(raw_payload.get(AIigConfigurationProviderDocumentPayload_1.SCHEMA_FIELD_NAME__VALUES, {}), "payload.values")),
            policies=policies,
            metadata=dict(_mapping(raw_payload.get(AIigConfigurationProviderDocumentPayload_1.SCHEMA_FIELD_NAME__METADATA, {}), "payload.metadata")),
        )
        revision = raw.get(AIigConfigurationProviderDocument_1.SCHEMA_FIELD_NAME__RECORD_REVISION)
        return AIcConfigurationProviderSnapshot(scope, target, revision, payload)

    @staticmethod
    def encode_change_set(change_set: AIcConfigurationChangeSet) -> dict[str, object]:
        return {
            "ConfigurationScope": {AIigConfigurationProviderDocumentConfigurationScope_1.SCHEMA_FIELD_NAME__TYPE: change_set.configuration_scope.type, AIigConfigurationProviderDocumentConfigurationScope_1.SCHEMA_FIELD_NAME__ID: change_set.configuration_scope.id},
            "ConfigurationProviderId": change_set.configuration_provider_id,
            "ConfigurationTarget": _encode_target(change_set.configuration_target),
            "ExpectedRecordRevision": change_set.expected_record_revision,
            "ConfigurationSchemaId": change_set.configuration_schema_id,
            "ConfigurationSchemaVersion": change_set.configuration_schema_version,
            "WrittenByComponentVersion": change_set.written_by_component_version,
            "Changes": [
                {
                    "PropertyId": change.property_id,
                    "Operation": change.operation.value,
                    **({"Value": copy.deepcopy(change.value)} if change.has_value else {}),
                    **({"PolicyModes": [
                        {"Mode": item.mode.value, "Value": copy.deepcopy(item.value)} for item in change.policy_modes
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
