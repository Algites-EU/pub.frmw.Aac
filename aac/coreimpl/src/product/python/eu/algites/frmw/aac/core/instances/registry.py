from __future__ import annotations
from dataclasses import replace
from uuid import uuid4
from eu.algites.frmw.aac.core.descriptor.api import AIcComponentDescriptor, AIcProviderDefinitionDescriptor
from eu.algites.frmw.aac.core.capability.api import AIcProvidedCapability
from eu.algites.frmw.aac.core.instances.api import AIcProviderInstance, AInProviderAccessMode, AInProviderInstanceState
from eu.algites.frmw.aac.core.persistence.api import AIcStateMutation, AIiStateStore
from eu.algites.frmw.aac.core.persistence.aic_in_memory_state_store import AIcInMemoryStateStore
from eu.algites.frmw.aac.core.persistence.state_store_support import state_delete_mutation, state_put_mutation

from .aic_provider_instance_registry import AIcProviderInstanceRegistry

_PROVIDER_NAMESPACE = "aac.provider-instances"

def instance_to_dict(instance: AIcProviderInstance) -> dict[str, object]:
    return _instance_to_dict(instance)

def _instance_to_dict(instance: AIcProviderInstance) -> dict[str, object]:
    return {
        "id": instance.id,
        "component_id": instance.component_id,
        "provider_definition_id": instance.provider_definition_id,
        "name": instance.name,
        "capabilities": [
            {"id": capability.id, "versions": list(capability.versions)}
            for capability in instance.capabilities
        ],
        "implementation_class": instance.implementation_class,
        "access_mode": instance.access_mode.value,
        "configuration": dict(instance.configuration),
        "configuration_schema": instance.configuration_schema,
        "state": instance.state.value,
    }

def _instance_from_dict(raw: dict[str, object] | object) -> AIcProviderInstance:
    if not isinstance(raw, dict):
        raise ValueError("persisted provider instance must be an object")
    return AIcProviderInstance(
        id=str(raw["id"]),
        component_id=str(raw["component_id"]),
        provider_definition_id=str(raw["provider_definition_id"]),
        name=str(raw["name"]),
        capabilities=tuple(
            AIcProvidedCapability(str(item["id"]), tuple(int(version) for version in item["versions"]))
            for item in raw["capabilities"]
        ),
        implementation_class=str(raw["implementation_class"]),
        access_mode=AInProviderAccessMode(str(raw.get("access_mode", AInProviderAccessMode.READ_WRITE.value))),
        configuration=dict(raw.get("configuration", {})),
        configuration_schema=str(raw["configuration_schema"]) if raw.get("configuration_schema") is not None else None,
        state=AInProviderInstanceState(str(raw.get("state", AInProviderInstanceState.CONFIGURED.value))),
    )
