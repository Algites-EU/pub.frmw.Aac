import json

from eu.algites.frmw.aac.core.observation.api import AIigObservationInput_1, AIngObservationInputPhase_1
from eu.algites.frmw.aac.observation.simpleaudit import AIcSimpleAuditObserver


def sample():
    from unittest.mock import Mock
    value = Mock(spec=AIigObservationInput_1)
    value.invocation_id = "inv-1"
    value.phase = AIngObservationInputPhase_1.PRE.value
    value.capability_id = "_AO.vcs.repository"
    value.capability_version = 1
    value.operation_id = "commit"
    value.provider_instance_id = "provider-1"
    value.to_mapping.return_value = {
        AIigObservationInput_1.SCHEMA_FIELD_NAME__INVOCATION_ID: value.invocation_id,
        AIigObservationInput_1.SCHEMA_FIELD_NAME__PHASE: value.phase,
        AIigObservationInput_1.SCHEMA_FIELD_NAME__CAPABILITY_ID: value.capability_id,
        AIigObservationInput_1.SCHEMA_FIELD_NAME__CAPABILITY_VERSION: value.capability_version,
        AIigObservationInput_1.SCHEMA_FIELD_NAME__OPERATION_ID: value.operation_id,
        AIigObservationInput_1.SCHEMA_FIELD_NAME__PROVIDER_INSTANCE_ID: value.provider_instance_id,
        AIigObservationInput_1.SCHEMA_FIELD_NAME__ARGUMENTS: {"Message": "test"},
    }
    return value

def test_stdout_json(capsys):
    provider = AIcSimpleAuditObserver({"Output": {"Type": "stdout"}, "Format": "json"})
    assert provider.observe_1(sample()).accepted
    payload = json.loads(capsys.readouterr().out)
    assert payload["OperationId"] == "commit"
    assert payload["Phase"] == "pre"


def test_file_output(tmp_path):
    path = tmp_path / "audit.log"
    provider = AIcSimpleAuditObserver({"Output": {"Type": "file", "Path": str(path)}, "Format": "text"})
    provider.observe_1(sample())
    text = path.read_text()
    assert "_AO.vcs.repository/1 commit" in text
    assert "invocation=inv-1" in text
