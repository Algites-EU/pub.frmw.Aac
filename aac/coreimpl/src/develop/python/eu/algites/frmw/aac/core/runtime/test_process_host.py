from eu.algites.frmw.aac.core.observation.aicgd_observation_output_1 import AIcgdObservationOutput_1
from eu.algites.frmw.aac.core.observation.aicgd_observation_input_1 import AIcgdObservationInput_1
from eu.algites.frmw.aac.core.invocation.api import AIcInvocationInput
from eu.algites.frmw.aac.core.observation.api import (
    AIigObservationInput_1,
    AIigObservationOutput_1,
    AIngObservationInputPhase_1,
)
from eu.algites.frmw.aac.core.runtime.process_host import _invoke_runtime


class ObserverRuntime:
    def __init__(self):
        self.received = None

    def observe_1(self, observation_input: AIigObservationInput_1) -> AIigObservationOutput_1:
        self.received = observation_input
        return AIcgdObservationOutput_1(accepted=True)


def test_process_runtime_coerces_direct_operation_object_to_typed_dataclass():
    runtime = ObserverRuntime()
    invocation = AIcInvocationInput(
        invocation_id="delivery",
        parent_invocation_id=None,
        capability_id="_AAC.capability.observation",
        capability_version=1,
        operation_id="observe",
        provider_instance_id="observer",
        arguments={
            "InvocationId": "observed",
            "ParentInvocationId": None,
            "Phase": "pre",
            "CapabilityId": "x.cap",
            "CapabilityVersion": 1,
            "OperationId": "run",
            "ProviderInstanceId": "provider",
            "Arguments": {"Value": 7},
            "Metadata": {},
        },
    )

    output = _invoke_runtime(runtime, invocation)

    assert output.success
    assert output.result["Accepted"] is True
    assert isinstance(runtime.received, AIigObservationInput_1)
    assert isinstance(runtime.received, AIcgdObservationInput_1)
    assert runtime.received.phase == AIngObservationInputPhase_1.PRE.value
    assert runtime.received.arguments == {"Value": 7}
