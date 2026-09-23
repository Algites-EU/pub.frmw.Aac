import pytest
from algites.lib.aac.coreintf.contracts import AIcProvidedCapability
from algites.lib.aac.coreintf.descriptor import AIcComponentDescriptor, AIcProviderDefinitionDescriptor
from algites.lib.aac.coreintf.instances import AIcBinding
from algites.lib.aac.coreimpl.bindings import AIcBindingStore
from algites.lib.aac.coreimpl.errors import AIxProvisioningError
from algites.lib.aac.coreimpl.instances import AIcProviderInstanceRegistry
from algites.lib.aac.coreimpl.provisioning import AIcProvisioningEngine


def test_unprovision_rejects_instances_referenced_by_binding():
    registry = AIcProviderInstanceRegistry(); bindings = AIcBindingStore(registry.store)
    provider = AIcProviderDefinitionDescriptor("p", (AIcProvidedCapability("cap.x", (1,)),), "x:P")
    descriptor = AIcComponentDescriptor("component", 1, (provider,))
    instance = registry.create("component", provider)
    bindings.put(AIcBinding("consumer", "r", instance.id, "cap.x", 1))
    engine = AIcProvisioningEngine(registry, store=registry.store, binding_store=bindings)
    with pytest.raises(AIxProvisioningError, match="bindings"):
        engine.unprovision("app", descriptor)
