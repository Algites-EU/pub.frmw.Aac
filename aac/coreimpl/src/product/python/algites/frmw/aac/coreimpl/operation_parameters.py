from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

from jsonschema import Draft202012Validator

from algites.frmw.aac.coreintf.descriptor import (
    AIcOperationParameterDefinitionDescriptor,
    AIcProviderDefinitionDescriptor,
)
from algites.frmw.aac.coreintf.persistence import AIiStateStore

_OPERATION_PARAMETER_CONFIGURATION_NAMESPACE = "aac.operation-parameter-configuration"


@dataclass(frozen=True, slots=True)
class AIcConfiguredOperationParameterValue:
    value: object
    written_by_component_version: int


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


class AIcOperationParameterResolver:
    """Resolve definition default -> component -> provider instance -> invocation override."""

    def __init__(self, configuration_store: AIcOperationParameterConfigurationStore) -> None:
        self.configuration_store = configuration_store

    @staticmethod
    def validate_definition(parameter: AIcOperationParameterDefinitionDescriptor) -> None:
        Draft202012Validator.check_schema(dict(parameter.value_schema))
        validator = Draft202012Validator(dict(parameter.value_schema))
        if parameter.has_default:
            validator.validate(parameter.default)
        enum_declared = parameter.value_schema.get("enum")
        if parameter.enum_values and not isinstance(enum_declared, list):
            raise ValueError(f"operation parameter {parameter.id!r} has enum_values but value_schema has no enum")
        if isinstance(enum_declared, list):
            declared = {json.dumps(value, sort_keys=True, default=str) for value in enum_declared}
            described = {json.dumps(item.value, sort_keys=True, default=str) for item in parameter.enum_values}
            if described - declared:
                raise ValueError(f"operation parameter {parameter.id!r} describes enum values absent from value_schema")

    @classmethod
    def validate_provider_definition(cls, provider: AIcProviderDefinitionDescriptor) -> None:
        for operation in provider.operations:
            for parameter in operation.parameters:
                cls.validate_definition(parameter)

    @staticmethod
    def _validate_value(parameter: AIcOperationParameterDefinitionDescriptor, value: object) -> object:
        Draft202012Validator(dict(parameter.value_schema)).validate(value)
        return value

    def resolve(
        self,
        provider: AIcProviderDefinitionDescriptor,
        *,
        component_id: str,
        component_version: int,
        provider_instance_id: str,
        capability_id: str,
        capability_version: int,
        operation_id: str,
        invocation_overrides: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        definition = provider.operation_parameter_definition(capability_id, capability_version, operation_id)
        overrides = dict(invocation_overrides or {})
        if definition is None:
            if overrides:
                raise ValueError("operation does not declare provider-specific operation parameters")
            return {}
        parameters = {item.id: item for item in definition.parameters}
        unknown = set(overrides) - set(parameters)
        if unknown:
            raise ValueError(f"unknown operation parameter overrides: {sorted(unknown)!r}")
        result: dict[str, object] = {}
        for parameter in definition.parameters:
            value = parameter.default if parameter.has_default else None
            has_value = parameter.has_default
            component_value = self.configuration_store.component_value(
                component_id, provider.id, capability_id, capability_version, operation_id, parameter.id
            )
            if component_value is not None:
                if not parameter.component_configurable:
                    raise ValueError(f"operation parameter {parameter.id!r} is not component-configurable")
                value = component_value.value
                has_value = True
            instance_value = self.configuration_store.instance_value(
                component_id, provider.id, provider_instance_id, capability_id,
                capability_version, operation_id, parameter.id
            )
            if instance_value is not None:
                if not parameter.instance_configurable:
                    raise ValueError(f"operation parameter {parameter.id!r} is not instance-configurable")
                value = instance_value.value
                has_value = True
            if parameter.id in overrides:
                if not parameter.invocation_overridable:
                    raise ValueError(f"operation parameter {parameter.id!r} is not invocation-overridable")
                value = overrides[parameter.id]
                has_value = True
            if parameter.required and not has_value:
                raise ValueError(f"required operation parameter {parameter.id!r} has no effective value")
            if has_value:
                result[parameter.id] = self._validate_value(parameter, value)
        return result

    def validate_configured_value(
        self, parameter: AIcOperationParameterDefinitionDescriptor, value: object, *, scope: str
    ) -> None:
        if scope == "COMPONENT" and not parameter.component_configurable:
            raise ValueError(f"operation parameter {parameter.id!r} is not component-configurable")
        if scope == "PROVIDER_INSTANCE" and not parameter.instance_configurable:
            raise ValueError(f"operation parameter {parameter.id!r} is not instance-configurable")
        self._validate_value(parameter, value)
