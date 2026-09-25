from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Mapping
from jsonschema import Draft202012Validator
from eu.algites.frmw.aac.core.descriptor.api import (
    AIcOperationParameterDefinitionDescriptor,
    AIcProviderDefinitionDescriptor,
)
from eu.algites.frmw.aac.core.persistence.api import AIiStateStore

from .aic_configured_operation_parameter_value import AIcConfiguredOperationParameterValue

_OPERATION_PARAMETER_CONFIGURATION_NAMESPACE = "aac.operation-parameter-configuration"

class AIcOperationParameterConfigurationStore:
    """Core-owned persisted component/instance defaults for provider operation parameters."""

    def __init__(self, store: AIiStateStore) -> None:
        self.store = store

    @staticmethod
    def _key(
        scope: str,
        component_id: str,
        provider_definition_id: str,
        capability_id: str,
        capability_version: int,
        operation_id: str,
        parameter_id: str,
        provider_instance_id: str | None = None,
    ) -> str:
        return json.dumps(
            [scope, component_id, provider_definition_id, provider_instance_id, capability_id,
             capability_version, operation_id, parameter_id],
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def _put(self, key: str, value: object, component_version: int) -> None:
        self.store.put(_OPERATION_PARAMETER_CONFIGURATION_NAMESPACE, key, {
            "value": value,
            "written_by_component_version": component_version,
        })

    def set_component_value(
        self, component_id: str, provider_definition_id: str, capability_id: str,
        capability_version: int, operation_id: str, parameter_id: str, value: object,
        *, component_version: int,
    ) -> None:
        self._put(self._key(
            "COMPONENT", component_id, provider_definition_id, capability_id,
            capability_version, operation_id, parameter_id,
        ), value, component_version)

    def set_instance_value(
        self, component_id: str, provider_definition_id: str, provider_instance_id: str,
        capability_id: str, capability_version: int, operation_id: str, parameter_id: str,
        value: object, *, component_version: int,
    ) -> None:
        self._put(self._key(
            "PROVIDER_INSTANCE", component_id, provider_definition_id, capability_id,
            capability_version, operation_id, parameter_id, provider_instance_id,
        ), value, component_version)

    def delete_component_value(
        self, component_id: str, provider_definition_id: str, capability_id: str,
        capability_version: int, operation_id: str, parameter_id: str,
    ) -> None:
        self.store.delete(_OPERATION_PARAMETER_CONFIGURATION_NAMESPACE, self._key(
            "COMPONENT", component_id, provider_definition_id, capability_id,
            capability_version, operation_id, parameter_id,
        ))

    def delete_instance_value(
        self, component_id: str, provider_definition_id: str, provider_instance_id: str,
        capability_id: str, capability_version: int, operation_id: str, parameter_id: str,
    ) -> None:
        self.store.delete(_OPERATION_PARAMETER_CONFIGURATION_NAMESPACE, self._key(
            "PROVIDER_INSTANCE", component_id, provider_definition_id, capability_id,
            capability_version, operation_id, parameter_id, provider_instance_id,
        ))

    def _get(self, key: str) -> AIcConfiguredOperationParameterValue | None:
        raw = self.store.get(_OPERATION_PARAMETER_CONFIGURATION_NAMESPACE, key)
        if raw is None:
            return None
        return AIcConfiguredOperationParameterValue(
            raw.get("value"), int(raw["written_by_component_version"])
        )

    def component_value(
        self, component_id: str, provider_definition_id: str, capability_id: str,
        capability_version: int, operation_id: str, parameter_id: str,
    ) -> AIcConfiguredOperationParameterValue | None:
        return self._get(self._key(
            "COMPONENT", component_id, provider_definition_id, capability_id,
            capability_version, operation_id, parameter_id,
        ))

    def instance_value(
        self, component_id: str, provider_definition_id: str, provider_instance_id: str,
        capability_id: str, capability_version: int, operation_id: str, parameter_id: str,
    ) -> AIcConfiguredOperationParameterValue | None:
        return self._get(self._key(
            "PROVIDER_INSTANCE", component_id, provider_definition_id, capability_id,
            capability_version, operation_id, parameter_id, provider_instance_id,
        ))
