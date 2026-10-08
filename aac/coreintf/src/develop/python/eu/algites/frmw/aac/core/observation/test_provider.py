import pytest
from unittest.mock import Mock

from eu.algites.frmw.aac.core.observation.api import AIigObservationInput_1, AIigObservationOutput_1, AIngObservationInputPhase_1, AIiObservationProvider


class BrokenObserver(AIiObservationProvider):
    pass


class GoodObserver(AIiObservationProvider):
    def observe_1(self, observation_input: AIigObservationInput_1) -> AIigObservationOutput_1:
        return Mock(spec=AIigObservationOutput_1, accepted=True)


def test_observation_provider_is_abstract():
    with pytest.raises(TypeError):
        BrokenObserver()


def test_observation_provider_can_be_implemented():
    provider = GoodObserver()
    value = provider.observe_1(Mock(spec=AIigObservationInput_1))
    assert value.accepted
