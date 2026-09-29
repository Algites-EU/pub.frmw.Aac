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
        "Id": instance.id,
        "ComponentId": instance.component_id,
        "ProviderDefinitionId": instance.provider_definition_id,
        "Name": instance.name,
        "Capabilities": [
            {"Id": capability.id, "Versions": list(capability.versions)}
            for capability in instance.capabilities
        ],
        "ImplementationClass": instance.implementation_class,
        "CapabilityProfileMatcherClass": instance.capability_profile_matcher_class,
        "AccessMode": instance.access_mode.value,
        "Configuration": dict(instance.configuration),
        "ConfigurationSchema": instance.configuration_schema,
        "State": instance.state.value,
    }

def _instance_from_dict(raw: dict[str, object] | object) -> AIcProviderInstance:
    if not isinstance(raw, dict):
        raise ValueError("persisted provider instance must be an object")
    return AIcProviderInstance(
        id=str(raw["Id"]),
        component_id=str(raw["ComponentId"]),
        provider_definition_id=str(raw["ProviderDefinitionId"]),
        name=str(raw["Name"]),
        capabilities=tuple(
            AIcProvidedCapability(str(item["Id"]), tuple(int(version) for version in item["Versions"]))
            for item in raw["Capabilities"]
        ),
        implementation_class=str(raw["ImplementationClass"]),
        capability_profile_matcher_class=(str(raw["CapabilityProfileMatcherClass"]) if raw.get("CapabilityProfileMatcherClass") is not None else None),
        access_mode=AInProviderAccessMode(str(raw.get("AccessMode", AInProviderAccessMode.READ_WRITE.value))),
        configuration=dict(raw.get("Configuration", {})),
        configuration_schema=str(raw["ConfigurationSchema"]) if raw.get("ConfigurationSchema") is not None else None,
        state=AInProviderInstanceState(str(raw.get("State", AInProviderInstanceState.CONFIGURED.value))),
    )
