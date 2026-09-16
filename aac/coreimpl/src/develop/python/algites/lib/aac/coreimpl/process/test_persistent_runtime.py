from __future__ import annotations

import os
from dataclasses import dataclass

from algites.lib.aac.coreintf.contracts import AInConsumerCardinality
from algites.lib.aac.coreintf.descriptor import (
    AIcConsumerRequirementDescriptor,
    AIcProviderDefinitionDescriptor,
    AIcProviderRuntimeDescriptor,
    AInProviderRuntimeProfile,
)
from algites.lib.aac.coreintf.instances import AIcBinding, AIcProviderInstance
from algites.lib.aac.coreintf.invocation import AIiCapabilityHandle, AIcInvocationInput, AIcInvocationOutput
from algites.lib.aac.coreimpl.process import AIcProcessProviderRuntime
from algites.lib.aac.coreimpl.invocation import _CURRENT_INVOCATION_ID

SEEN_PARENTS = []


@dataclass
class AIcFakeHandle(AIiCapabilityHandle):
    _binding: AIcBinding

    @property
    def binding(self) -> AIcBinding:
        return self._binding

    def invoke(self, operation_id: str, arguments=None) -> AIcInvocationOutput:
        SEEN_PARENTS.append(_CURRENT_INVOCATION_ID.get())
        assert operation_id == "echo"
        return AIcInvocationOutput(True, result={"echo": dict(arguments or {}).get("value")})


def test_persistent_process_supports_nested_core_capability_calls(tmp_path, monkeypatch):
    SEEN_PARENTS.clear()
    module = tmp_path / "aac_process_fixture.py"
    module.write_text(
        """
from algites.lib.aac.coreintf.runtime import AIiProviderRuntime

class AIcProcessFixtureProvider(AIiProviderRuntime):
    def __init__(self, configuration=None):
        self.dep = None
    def wire(self, bindings):
        self.dep = bindings['dep'][0]
    def use_dependency(self, value):
        result = self.dep.invoke('echo', {'value': value})
        if not result.success:
            raise RuntimeError(str(result.error))
        return {'nested': result.result}
""",
        encoding="utf-8",
    )
    existing = os.environ.get("PYTHONPATH", "")
    pythonpath = str(tmp_path) + (os.pathsep + existing if existing else "")
    provider = AIcProviderDefinitionDescriptor(
        id="consumer",
        capability_id="example.consumer",
        capability_versions=(1,),
        implementation_class="aac_process_fixture:AIcProcessFixtureProvider",
        requirements=(AIcConsumerRequirementDescriptor("dep", "example.echo", (1,), AInConsumerCardinality.SINGLE, True),),
        runtime=AIcProviderRuntimeDescriptor(
            profile=AInProviderRuntimeProfile.PROCESS,
            environment={"PYTHONPATH": pythonpath},
        ),
    )
    instance = AIcProviderInstance(
        id="consumer-1",
        component_id="example.component",
        provider_definition_id="consumer",
        name="default",
        capability_id="example.consumer",
        capability_versions=(1,),
        implementation_class=provider.implementation_class,
    )
    runtime = AIcProcessProviderRuntime("app", instance, provider)
    try:
        binding = AIcBinding("consumer-1", "dep", "echo-1", "example.echo", 1)
        runtime.wire({"dep": (AIcFakeHandle(binding),)})
        runtime.prepare_activation()
        runtime.activate()
        pid = runtime.process_id
        first = runtime.invoke(AIcInvocationInput("i1", None, "example.consumer", 1, "use_dependency", "consumer-1", {"value": "one"}))
        second = runtime.invoke(AIcInvocationInput("i2", None, "example.consumer", 1, "use_dependency", "consumer-1", {"value": "two"}))
        assert first.success and first.result == {"nested": {"echo": "one"}}
        assert second.success and second.result == {"nested": {"echo": "two"}}
        assert runtime.process_id == pid
        assert runtime.is_running
        assert SEEN_PARENTS == ["i1", "i2"]
    finally:
        runtime.deactivate("test complete")
        runtime.close()
    assert not runtime.is_running
