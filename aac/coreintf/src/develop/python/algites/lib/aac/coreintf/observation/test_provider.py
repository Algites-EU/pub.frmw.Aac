import pytest

from algites.lib.aac.coreintf.observation import AIcObservationInput, AIcObservationOutput, AInObservationPhase, AIiObservationProvider


class BrokenObserver(AIiObservationProvider):
    pass


class GoodObserver(AIiObservationProvider):
    def observe_1(self, observation_input: AIcObservationInput) -> AIcObservationOutput:
        return AIcObservationOutput()


def test_observation_provider_is_abstract():
    with pytest.raises(TypeError):
        BrokenObserver()


def test_observation_provider_can_be_implemented():
    provider = GoodObserver()
    value = provider.observe_1(AIcObservationInput(
        invocation_id="i", parent_invocation_id=None, phase=AInObservationPhase.PRE,
        capability_id="x", capability_version=1, operation_id="op", provider_instance_id="p",
    ))
    assert value.accepted
