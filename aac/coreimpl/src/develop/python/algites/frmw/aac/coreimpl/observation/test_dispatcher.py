from algites.frmw.aac.coreintf.observation import (
    AIcObservationBinding,
    AIcObservationInput,
    AIcObservationSelector,
    AInObservationPhase,
)
from algites.frmw.aac.coreimpl.core import AIcApplicationComponentCore


def test_end_to_end_simpleaudit_plugin_is_loaded_through_coreintf():
    core = AIcApplicationComponentCore()
    core.install_aac_package("algites.frmw.aac.simpleaudit")
    core.activate_application("app")
    instance = core.instances.find(component_id="_AAC.component.simpleaudit")[0]
    core.configure_observer(AIcObservationBinding(instance.id, (AIcObservationSelector(capability="_AO.vcs.*"),)))
    deliveries = core.observations.dispatch(AIcObservationInput(
        invocation_id="1", parent_invocation_id=None, phase=AInObservationPhase.PRE,
        capability_id="_AO.vcs.repository", capability_version=1, operation_id="status",
        provider_instance_id="vcs-1", arguments={"repository": "x"},
    ))
    try:
        assert deliveries[0].output is not None and deliveries[0].output.accepted
    finally:
        core.lifecycle.deactivate_instance(instance.id, "test complete")


def test_observation_capability_never_observes_itself():
    core = AIcApplicationComponentCore()
    core.install_aac_package("algites.frmw.aac.simpleaudit")
    core.activate_application("app")
    instance = core.instances.find(component_id="_AAC.component.simpleaudit")[0]
    # Self-observation is forbidden at topology validation level, so use a wildcard selector.
    core.configure_observer(AIcObservationBinding(instance.id, (AIcObservationSelector(capability="*"),)))
    deliveries = core.observations.dispatch(AIcObservationInput(
        invocation_id="1", parent_invocation_id=None, phase=AInObservationPhase.PRE,
        capability_id="_AAC.capability.observation", capability_version=1, operation_id="observe",
        provider_instance_id=instance.id,
    ))
    try:
        assert deliveries == ()
    finally:
        core.lifecycle.deactivate_instance(instance.id, "test complete")
