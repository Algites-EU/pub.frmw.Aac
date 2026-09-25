from algites.frmw.aac.coreintf.invocation import AIcInvocationInput
from algites.frmw.aac.coreintf.observation import (
    AIcObservationInput,
    AIcObservationOutput,
    AInObservationPhase,
)
from algites.frmw.aac.coreintf.runtime.process_host import _invoke_runtime


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
            "invocation_id": "observed",
            "parent_invocation_id": None,
            "phase": "PRE",
            "capability_id": "x.cap",
            "capability_version": 1,
            "operation_id": "run",
            "provider_instance_id": "provider",
            "arguments": {"value": 7},
            "outcome": None,
            "result": None,
            "error": None,
            "metadata": {},
        },
    )

    output = _invoke_runtime(runtime, invocation)

    assert output.success
    assert output.result["accepted"] is True
    assert isinstance(runtime.received, AIcObservationInput)
    assert runtime.received.phase is AInObservationPhase.PRE
    assert runtime.received.arguments == {"value": 7}
