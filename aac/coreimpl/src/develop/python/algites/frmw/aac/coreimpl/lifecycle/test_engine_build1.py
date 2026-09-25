from algites.frmw.aac.coreintf.instances import AInProviderInstanceState
from algites.frmw.aac.coreintf.lifecycle import AInLifecycleState
from algites.frmw.aac.coreimpl.core import AIcApplicationComponentCore


def test_simpleaudit_runs_complete_lifecycle_with_declarative_configuration_defaults():
    core = AIcApplicationComponentCore()
    installed = core.install_aac_package("algites.frmw.aac.simpleaudit")
    outcome = core.lifecycle.activate("app", installed.discovered)
    assert outcome.status.state is AInLifecycleState.ACTIVE
    instances = core.instances.find(component_id="_AAC.component.simpleaudit")
    assert len(instances) == 1
    assert instances[0].state is AInProviderInstanceState.ACTIVE
    assert instances[0].configuration["format"] == "JSON"


def test_suspend_and_deactivate_preserve_provider_instance_identity():
    core = AIcApplicationComponentCore()
    installed = core.install_aac_package("algites.frmw.aac.simpleaudit")
    outcome = core.lifecycle.activate("app", installed.discovered)
    instance_id = outcome.runtime_instance_ids[0]
    assert core.lifecycle.suspend("app", installed.descriptor, "maintenance").state is AInLifecycleState.SUSPENDED
    assert core.instances.get(instance_id).state is AInProviderInstanceState.SUSPENDED
    assert core.lifecycle.deactivate("app", installed.descriptor, "stop").state is AInLifecycleState.DEACTIVATED
    assert core.instances.get(instance_id).id == instance_id
