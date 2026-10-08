"""The Modustro generator owns both the observation interface and its DTO."""
from __future__ import annotations

import dataclasses

from eu.algites.frmw.aac.core.observation.api import (
    AIigObservationInput_1, AIngObservationInputPhase_1, AIngObservationInputOutcome_1,
)
from eu.algites.frmw.aac.core.observation.aicgd_observation_input_1 import AIcgdObservationInput_1


def test_generated_observation_contract_and_roundtrip():
    original = AIcgdObservationInput_1(
        invocation_id="inv", phase=AIngObservationInputPhase_1.PRE.value,
        capability_id="x", capability_version=1, operation_id="run", provider_instance_id="p",
        arguments={"Value": 3}, outcome=AIngObservationInputOutcome_1.SUCCESS.value,
    )
    assert isinstance(original, AIigObservationInput_1)
    assert dataclasses.is_dataclass(original)
    wire = original.to_mapping()
    assert wire[AIigObservationInput_1.SCHEMA_FIELD_NAME__PHASE] == AIngObservationInputPhase_1.PRE.value
    assert wire[AIigObservationInput_1.SCHEMA_FIELD_NAME__OUTCOME] == AIngObservationInputOutcome_1.SUCCESS.value
    assert AIcgdObservationInput_1.from_mapping(wire) == original
    assert AIigObservationInput_1.SCHEMA_FIELD_NAME__INVOCATION_ID in wire


def test_generated_observation_is_accepted_by_simpleaudit(capsys):
    import json
    from eu.algites.frmw.aac.observation.simpleaudit import AIcSimpleAuditObserver

    event = AIcgdObservationInput_1(
        invocation_id="audit-inv", phase=AIngObservationInputPhase_1.POST.value,
        capability_id="core.example", capability_version=1,
        operation_id="do", provider_instance_id="provider",
        arguments={}, outcome=AIngObservationInputOutcome_1.SUCCESS.value,
    )
    observer = AIcSimpleAuditObserver({"Format": "json"})
    assert observer.observe_1(event).accepted
    assert json.loads(capsys.readouterr().out) == event.to_mapping()
