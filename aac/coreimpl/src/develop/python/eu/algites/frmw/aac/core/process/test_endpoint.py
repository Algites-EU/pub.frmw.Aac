import sys

from eu.algites.frmw.aac.core.invocation.api import AIcInvocationInput
from eu.algites.frmw.aac.core.runtime.process import AIcJsonLineProcessEndpoint


def test_json_line_process_endpoint_can_call_isolated_external_runtime(tmp_path):
    script = tmp_path / "peer.py"
    script.write_text(
        "import json,sys\n"
        "v=json.loads(sys.stdin.readline())\n"
        "print(json.dumps({'Success': True, 'Result': {'Operation': v['OperationId'], 'Value': v['Arguments']['Value']}}))\n",
        encoding="utf-8",
    )
    endpoint = AIcJsonLineProcessEndpoint([sys.executable, str(script)])
    result = endpoint.invoke(AIcInvocationInput("i", None, "x", 1, "work", "p", {"Value": 7}))
    assert result.success
    assert result.result == {"Operation": "work", "Value": 7}
