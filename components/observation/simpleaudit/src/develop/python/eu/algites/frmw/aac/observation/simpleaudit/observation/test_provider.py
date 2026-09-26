import json

from eu.algites.frmw.aac.core.observation.api import AIcObservationInput, AInObservationPhase
from eu.algites.frmw.aac.observation.simpleaudit import AIcSimpleAuditObserver


def sample():
    return AIcObservationInput(
        invocation_id="inv-1", parent_invocation_id=None, phase=AInObservationPhase.PRE,
        capability_id="_AO.vcs.repository", capability_version=1, operation_id="commit",
        provider_instance_id="provider-1", arguments={"Message": "test"},
    )


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
