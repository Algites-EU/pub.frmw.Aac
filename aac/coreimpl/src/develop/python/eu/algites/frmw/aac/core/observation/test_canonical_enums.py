from eu.algites.frmw.aac.core.observation.aicgd_observation_input_1 import AIcgdObservationInput_1
"""Canonical observation enums are generated once from their JSON/YAML schema."""

import json
from pathlib import Path

import pytest

from eu.algites.frmw.aac.core.observation.api import (
    AIigObservationInput_1,
    AIngObservationInputPhase_1,
    AIngObservationInputOutcome_1,
)


def test_observation_enums_match_schema_and_wire_roundtrip():
    schema_file = (Path(__file__).resolve().parents[9].parent / "coreintf"
        / "src/product/jsondefs/eu/algites/frmw/aac/core/observation/observation-input_1.jsondef.schema.json")
    assert schema_file.exists(), schema_file
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    assert [item.value for item in AIngObservationInputPhase_1] == schema["properties"]["Phase"]["enum"]
    assert [item.value for item in AIngObservationInputOutcome_1 if item.value != "null"] == [
        item for item in schema["properties"]["Outcome"]["enum"] if item is not None
    ]
    assert AIngObservationInputPhase_1.PRE.value == "pre"
    assert AIngObservationInputOutcome_1.SUCCESS.value == "success"
    for phase in AIngObservationInputPhase_1:
        original = AIcgdObservationInput_1(
            invocation_id="i", parent_invocation_id=None, phase=phase.value, capability_id="x",
            capability_version=1, operation_id="run", provider_instance_id="p",
            outcome=AIngObservationInputOutcome_1.SUCCESS.value,
        )
        assert AIcgdObservationInput_1.from_mapping(original.to_mapping()) == original
        assert original.to_mapping()[AIigObservationInput_1.SCHEMA_FIELD_NAME__PHASE] == phase.value
        assert original.to_mapping()[AIigObservationInput_1.SCHEMA_FIELD_NAME__OUTCOME] == AIngObservationInputOutcome_1.SUCCESS.value
    with pytest.raises(ValueError):
        AIngObservationInputPhase_1("PRE")
