from eu.algites.frmw.aac.core.invocation.api import AIcInvocationInput
from eu.algites.frmw.aac.core.observation.api import (
    AIcObservationInput,
    AIcObservationOutput,
    AInObservationPhase,
)
from eu.algites.frmw.aac.core.runtime.process_host import _invoke_runtime


class ObserverRuntime:
    def __init__(self):
        self.received = None

    def observe_1(self, observation_input: AIcObservationInput) -> AIcObservationOutput:
        self.received = observation_input
        return AIcObservationOutput(accepted=True)


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
            "Outcome": None,
            "Result": None,
            "Error": None,
            "Metadata": {},
        },
    )

    output = _invoke_runtime(runtime, invocation)

    assert output.success
    assert output.result["Accepted"] is True
    assert isinstance(runtime.received, AIcObservationInput)
    assert runtime.received.phase is AInObservationPhase.PRE
    assert runtime.received.arguments == {"Value": 7}
