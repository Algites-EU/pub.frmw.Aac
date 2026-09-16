import sys

from algites.lib.aac.coreintf.invocation import AIcInvocationInput
from algites.lib.aac.coreimpl.process import AIcJsonLineProcessEndpoint


def test_json_line_process_endpoint_can_call_isolated_external_runtime(tmp_path):
    script = tmp_path / "peer.py"
    script.write_text(
        "import json,sys\n"
        "v=json.loads(sys.stdin.readline())\n"
        "print(json.dumps({'success': True, 'result': {'operation': v['operation_id'], 'value': v['arguments']['value']}}))\n",
        encoding="utf-8",
    )
    endpoint = AIcJsonLineProcessEndpoint([sys.executable, str(script)])
    result = endpoint.invoke(AIcInvocationInput("i", None, "x", 1, "work", "p", {"value": 7}))
    assert result.success
    assert result.result == {"operation": "work", "value": 7}
