from __future__ import annotations

import os
from dataclasses import dataclass

from eu.algites.frmw.aac.core.capability.api import AIcProvidedCapability, AInConsumerCardinality
from eu.algites.frmw.aac.core.descriptor.api import (
    AIcConsumerRequirementDescriptor,
    AIcProviderDefinitionDescriptor,
    AIcProviderImplementationClassDescriptor,
    AIcProviderRuntimeDescriptor,
    AInProviderRuntimeProfile,
)
from eu.algites.frmw.aac.core.instances.api import AIcBinding, AIcProviderInstance
from eu.algites.frmw.aac.core.invocation.api import AIiCapabilityHandle, AIcInvocationInput, AIcInvocationOutput
from eu.algites.frmw.aac.core.runtime.process import AIcProcessProviderRuntime
from eu.algites.frmw.aac.core.invocation.dispatcher import _CURRENT_INVOCATION_ID

SEEN_PARENTS = []


@dataclass
class AIcFakeHandle(AIiCapabilityHandle):
    _binding: AIcBinding

    @property
    def binding(self) -> AIcBinding:
        return self._binding

    def invoke(
        self, operation_id: str, arguments=None, *, operation_parameters=None, operation_interaction=None, locale=None
    ) -> AIcInvocationOutput:
        SEEN_PARENTS.append(_CURRENT_INVOCATION_ID.get())
        assert operation_id == "echo"
        return AIcInvocationOutput(True, result={"echo": dict(arguments or {}).get("value")})

    def start(
        self, operation_id: str, arguments=None, *, operation_parameters=None, operation_interaction=None, locale=None
    ):
        if operation_interaction is None:
            raise ValueError("test fake asynchronous invocation requires an explicit interaction")
        self.invoke(
            operation_id, arguments, operation_parameters=operation_parameters,
            operation_interaction=operation_interaction, locale=locale,
        )
        return operation_interaction


def test_persistent_process_supports_nested_core_capability_calls(tmp_path, monkeypatch):
    SEEN_PARENTS.clear()
    module = tmp_path / "aac_process_fixture.py"
    module.write_text(
        """
from eu.algites.frmw.aac.core.runtime.api import AIiProviderRuntime

class AIcProcessFixtureProvider(AIiProviderRuntime):
    def __init__(self, configuration=None):
        self.dep = None
    def wire(self, bindings):
        self.dep = bindings['dep'][0]
    def use_dependency_1(self, value):
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
        capabilities=(AIcProvidedCapability("example.consumer", (1,)),),
        implementation_classes=(AIcProviderImplementationClassDescriptor("python", "aac_process_fixture:AIcProcessFixtureProvider"),),
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
        capabilities=(AIcProvidedCapability("example.consumer", (1,)),),
        implementation_class=provider.implementation_class_for("python"),
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


def test_persistent_process_receives_effective_operation_parameters(tmp_path):
    module = tmp_path / "aac_process_operation_parameters_fixture.py"
    module.write_text(
        """
from eu.algites.frmw.aac.core.invocation.api import current_operation_parameters
from eu.algites.frmw.aac.core.runtime.api import AIiProviderRuntime

class AIcProcessOperationParametersProvider(AIiProviderRuntime):
    def __init__(self, configuration=None):
        pass
    def run_1(self, value):
        return {"value": value, "parameters": dict(current_operation_parameters())}
""",
        encoding="utf-8",
    )
    existing = os.environ.get("PYTHONPATH", "")
    pythonpath = str(tmp_path) + (os.pathsep + existing if existing else "")
    provider = AIcProviderDefinitionDescriptor(
        id="parameters",
        capabilities=(AIcProvidedCapability("example.parameters", (1,)),),
        implementation_classes=(AIcProviderImplementationClassDescriptor("python", "aac_process_operation_parameters_fixture:AIcProcessOperationParametersProvider"),),
        runtime=AIcProviderRuntimeDescriptor(
            profile=AInProviderRuntimeProfile.PROCESS,
            environment={"PYTHONPATH": pythonpath},
        ),
    )
    instance = AIcProviderInstance(
        id="parameters-1",
        component_id="example.component",
        provider_definition_id="parameters",
        name="default",
        capabilities=(AIcProvidedCapability("example.parameters", (1,)),),
        implementation_class=provider.implementation_class_for("python"),
    )
    runtime = AIcProcessProviderRuntime("app", instance, provider)
    try:
        output = runtime.invoke(AIcInvocationInput(
            "i", None, "example.parameters", 1, "run", "parameters-1", {"value": "x"},
            effective_operation_parameters={"strategy": "REBASE"},
        ))
        assert output.success
        assert output.result == {"value": "x", "parameters": {"strategy": "REBASE"}}
    finally:
        runtime.close()


def test_persistent_process_bridges_live_operation_interaction(tmp_path):
    from eu.algites.frmw.aac.core.invocation.api import (
        AInOperationInteractionDetailLevel,
        AInOperationInteractionMode,
        AIcOperationInteractionFeatures,
        operation_interaction_context,
    )
    from eu.algites.frmw.aac.core.interaction.controller import AIcOperationInteractionController

    module = tmp_path / "aac_process_interaction_fixture.py"
    module.write_text(
        """
from eu.algites.frmw.aac.core.invocation.api import (
    AInOperationInteractionEventType, AIcOperationInteractionEvent, AIcOperationInteractionFeatures,
    current_operation_interaction,
)
from eu.algites.frmw.aac.core.presentation.api import AIcDisplayText
from eu.algites.frmw.aac.core.runtime.api import AIiProviderRuntime

class AIcProcessInteractionProvider(AIiProviderRuntime):
    def __init__(self, configuration=None):
        pass
    def run_1(self, value):
        interaction = current_operation_interaction()
        interaction.declare_features(AIcOperationInteractionFeatures(
            progress_reporting=True, cancellation=True, detail_level=True, reporting_interval=True,
        ))
        interaction.report(AIcOperationInteractionEvent(
            AInOperationInteractionEventType.PROGRESS, progress_id="process-work", phase_id="process-work",
            name=AIcDisplayText(text="Process work"), current=1, total=3, unit="ITEMS",
        ))
        state = interaction.caller_snapshot()
        return {
            "value": value,
            "mode": state.interaction_mode.value,
            "detail": state.detail_level.value,
            "interval": state.reporting_interval_ms,
        }
""",
        encoding="utf-8",
    )
    existing = os.environ.get("PYTHONPATH", "")
    pythonpath = str(tmp_path) + (os.pathsep + existing if existing else "")
    provider = AIcProviderDefinitionDescriptor(
        id="interaction",
        capabilities=(AIcProvidedCapability("example.interaction", (1,)),),
        implementation_classes=(AIcProviderImplementationClassDescriptor("python", "aac_process_interaction_fixture:AIcProcessInteractionProvider"),),
        runtime=AIcProviderRuntimeDescriptor(
            profile=AInProviderRuntimeProfile.PROCESS,
            environment={"PYTHONPATH": pythonpath},
        ),
    )
    instance = AIcProviderInstance(
        id="interaction-1", component_id="example.component", provider_definition_id="interaction",
        name="default", capabilities=(AIcProvidedCapability("example.interaction", (1,)),),
        implementation_class=provider.implementation_class_for("python"),
    )
    messages = []
    interaction = AIcOperationInteractionController(messages.append)
    interaction.declare_features(AIcOperationInteractionFeatures(
        progress_reporting=True, cancellation=True, detail_level=True, reporting_interval=True,
    ))
    interaction.set_interaction_mode(AInOperationInteractionMode.BACKGROUND)
    interaction.set_detail_level(AInOperationInteractionDetailLevel.DETAILED)
    interaction.set_reporting_interval_ms(250)
    messages.clear()
    runtime = AIcProcessProviderRuntime("app", instance, provider)
    try:
        with operation_interaction_context(interaction):
            output = runtime.invoke(AIcInvocationInput(
                "interaction-invocation", None, "example.interaction", 1, "run", "interaction-1", {"value": "x"}
            ))
        assert output.success
        assert output.result == {"value": "x", "mode": "BACKGROUND", "detail": "DETAILED", "interval": 250}
        progress_events = [event for message in messages for event in message.events]
        assert len(progress_events) == 1 and progress_events[0].phase_id == "process-work"
        assert interaction.provider_snapshot().features.cancellation is True
    finally:
        runtime.close()
