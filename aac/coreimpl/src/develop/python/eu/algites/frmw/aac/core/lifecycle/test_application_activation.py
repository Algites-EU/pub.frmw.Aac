from eu.algites.frmw.aac.core.instances.api import AInProviderInstanceState
from eu.algites.frmw.aac.core.runtime.application import AIcApplicationComponentCore


def test_whole_application_activation_uses_provider_instance_lifecycle():
    core = AIcApplicationComponentCore()
    core.install_aac_package("eu.algites.frmw.aac.observation.simpleaudit")
    graph = core.activate_application("app")
    instance = core.instances.find(component_id="_AAC.component.simpleaudit")[0]
    assert instance.id in graph.provider_first_order
    assert core.instances.get(instance.id).state is AInProviderInstanceState.ACTIVE
    assert core.lifecycle.runtime(instance.id).__class__.__name__ == "AIcProcessProviderRuntime"
    assert core.lifecycle.runtime(instance.id).is_running
