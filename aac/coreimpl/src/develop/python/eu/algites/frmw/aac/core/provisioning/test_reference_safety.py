from eu.algites.frmw.aac.core.descriptor.api import AIcProviderImplementationClassDescriptor
import pytest
from eu.algites.frmw.aac.core.capability.api import AIcProvidedCapability
from eu.algites.frmw.aac.core.descriptor.api import AIcComponentDescriptor, AIcProviderDefinitionDescriptor
from eu.algites.frmw.aac.core.instances.api import AIcBinding
from eu.algites.frmw.aac.core.bindings.store import AIcBindingStore
from eu.algites.frmw.aac.core.implementation.errors import AIxProvisioningError
from eu.algites.frmw.aac.core.instances.registry import AIcProviderInstanceRegistry
from eu.algites.frmw.aac.core.provisioning.engine import AIcProvisioningEngine


def test_unprovision_rejects_instances_referenced_by_binding():
    registry = AIcProviderInstanceRegistry(); bindings = AIcBindingStore(registry.store)
    provider = AIcProviderDefinitionDescriptor("p", (AIcProvidedCapability("cap.x", (1,)),), (AIcProviderImplementationClassDescriptor("python", "x:P"),))
    descriptor = AIcComponentDescriptor("component", 1, (provider,))
    instance = registry.create("component", provider)
    bindings.put(AIcBinding("consumer", "r", instance.id, "cap.x", 1))
    engine = AIcProvisioningEngine(registry, store=registry.store, binding_store=bindings)
    with pytest.raises(AIxProvisioningError, match="bindings"):
        engine.unprovision("app", descriptor)
