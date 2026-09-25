from eu.algites.frmw.aac.core.observation.api import (
    AIcObservationBinding,
    AIcObservationInput,
    AIcObservationSelector,
    AInObservationPhase,
)
from eu.algites.frmw.aac.core.runtime.application import AIcApplicationComponentCore
from eu.algites.frmw.aac.core.runtime.process import AIcProcessProviderRuntime


def test_simpleaudit_observer_runs_in_persistent_process():
    core = AIcApplicationComponentCore()
    core.install_aac_package("eu.algites.frmw.aac.observation.simpleaudit")
    core.activate_application("app")
    instance = core.instances.find(component_id="_AAC.component.simpleaudit")[0]
    runtime = core.lifecycle.runtime(instance.id)
    assert isinstance(runtime, AIcProcessProviderRuntime)
    pid = runtime.process_id
    core.configure_observer(AIcObservationBinding(instance.id, (AIcObservationSelector(capability="example.*"),)))
    deliveries = core.observations.dispatch(AIcObservationInput(
        invocation_id="inv-1",
        parent_invocation_id=None,
        phase=AInObservationPhase.PRE,
        capability_id="example.demo",
        capability_version=1,
        operation_id="run",
        provider_instance_id="provider-1",
        arguments={"value": 1},
    ))
    assert len(deliveries) == 1
    assert deliveries[0].error is None
    assert deliveries[0].output is not None and deliveries[0].output.accepted
    assert runtime.process_id == pid and runtime.is_running
    core.lifecycle.deactivate_instance(instance.id, "test complete")
    assert not runtime.is_running


def test_two_provider_instances_use_two_processes():
    core = AIcApplicationComponentCore()
    installed = core.install_aac_package("eu.algites.frmw.aac.observation.simpleaudit")
    core.activate_application("app")
    first = core.instances.find(component_id="_AAC.component.simpleaudit")[0]
    provider = installed.descriptor.provider("observation")
    second = core.instances.create(
        installed.descriptor.id,
        provider,
        name="second",
        configuration={"output": {"type": "STDOUT"}, "format": "JSON"},
    )
    core.lifecycle.activate_instance("app", installed.descriptor, second.id, ())
    first_runtime = core.lifecycle.runtime(first.id)
    second_runtime = core.lifecycle.runtime(second.id)
    try:
        assert isinstance(first_runtime, AIcProcessProviderRuntime)
        assert isinstance(second_runtime, AIcProcessProviderRuntime)
        assert first_runtime.process_id != second_runtime.process_id
    finally:
        core.lifecycle.deactivate_instance(second.id, "test complete")
        core.lifecycle.deactivate_instance(first.id, "test complete")
