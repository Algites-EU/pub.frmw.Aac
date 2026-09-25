from algites.frmw.aac.coreintf.descriptor import AIcComponentDescriptor, AIcInitialProviderInstanceDescriptor, AIcProviderDefinitionDescriptor
from algites.frmw.aac.coreimpl.descriptor import AIcDescriptorLoader
from algites.frmw.aac.coreimpl.provisioning import AIcProvisioningEngine


def test_declarative_provisioning_creates_initial_instance_without_hook():
    descriptor = AIcDescriptorLoader.load_package("algites.frmw.aac.simpleaudit")
    engine = AIcProvisioningEngine()
    outcome = engine.provision("app", descriptor)
    assert len(outcome.created_instance_ids) == 1
    assert not outcome.hook_called
    assert engine.registry.get(outcome.created_instance_ids[0]).name == "default"


def test_reconciliation_does_not_duplicate_initial_instance():
    descriptor = AIcDescriptorLoader.load_package("algites.frmw.aac.simpleaudit")
    engine = AIcProvisioningEngine()
    first = engine.provision("app", descriptor)
    second = engine.provision("app", descriptor)
    assert len(first.created_instance_ids) == 1
    assert second.created_instance_ids == ()
    assert len(engine.registry.all()) == 1
