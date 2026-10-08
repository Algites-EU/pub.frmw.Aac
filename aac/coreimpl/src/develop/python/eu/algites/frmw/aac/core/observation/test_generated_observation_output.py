"""The ObservationOutput contract and DTO must be supplied by Modustro Codegen."""

from eu.algites.frmw.aac.core.observation.aiig_observation_output_1 import AIigObservationOutput_1
from eu.algites.frmw.aac.core.observation.aicgd_observation_output_1 import AIcgdObservationOutput_1


def test_generated_observation_output_contract_and_round_trip():
    output = AIcgdObservationOutput_1(accepted=True, diagnostic=None)
    assert isinstance(output, AIigObservationOutput_1)
    expected = {
        AIigObservationOutput_1.SCHEMA_FIELD_NAME__ACCEPTED: True,
        AIigObservationOutput_1.SCHEMA_FIELD_NAME__DIAGNOSTIC: None,
    }
    assert output.to_mapping() == expected
    assert AIcgdObservationOutput_1.from_mapping(expected) == output


def test_observation_output_missing_and_null_are_distinct():
    absent = AIcgdObservationOutput_1(accepted=True)
    assert absent.to_mapping() == {AIigObservationOutput_1.SCHEMA_FIELD_NAME__ACCEPTED: True}
    assert AIcgdObservationOutput_1.from_mapping(absent.to_mapping()) == absent
