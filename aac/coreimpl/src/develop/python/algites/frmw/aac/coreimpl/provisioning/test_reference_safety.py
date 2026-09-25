from algites.frmw.aac.coreintf.descriptor import AIcProviderImplementationClassDescriptor
import pytest
from algites.frmw.aac.coreintf.capability import AIcProvidedCapability
from algites.frmw.aac.coreintf.descriptor import AIcComponentDescriptor, AIcProviderDefinitionDescriptor
from algites.frmw.aac.coreintf.instances import AIcBinding
from algites.frmw.aac.coreimpl.bindings import AIcBindingStore
from algites.frmw.aac.coreimpl.errors import AIxProvisioningError
from algites.frmw.aac.coreimpl.instances import AIcProviderInstanceRegistry
from algites.frmw.aac.coreimpl.provisioning import AIcProvisioningEngine


def test_unprovision_rejects_instances_referenced_by_binding():
    registry = AIcProviderInstanceRegistry(); bindings = AIcBindingStore(registry.store)
    provider = AIcProviderDefinitionDescriptor("p", (AIcProvidedCapability("cap.x", (1,)),), (AIcProviderImplementationClassDescriptor("python", "x:P"),))
    descriptor = AIcComponentDescriptor("component", 1, (provider,))
    instance = registry.create("component", provider)
    bindings.put(AIcBinding("consumer", "r", instance.id, "cap.x", 1))
    engine = AIcProvisioningEngine(registry, store=registry.store, binding_store=bindings)
    with pytest.raises(AIxProvisioningError, match="bindings"):
        engine.unprovision("app", descriptor)
