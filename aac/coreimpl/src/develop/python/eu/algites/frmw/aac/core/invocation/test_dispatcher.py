from eu.algites.frmw.aac.core.capability.api import (
    AInCapabilityOperationInteractionKind,
    AIcCapabilityContract,
    AIcCapabilityOperation,
    AIcCapabilityOperationInteraction,
    AIcCapabilityRef,
    AIcSchemaRef,
)
from eu.algites.frmw.aac.core.invocation.api import AIcInvocationInput
from eu.algites.frmw.aac.core.observation.api import AIcObservationOutput, AIiObservationProvider
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.invocation.dispatcher import AIcInvocationDispatcher, AIcObjectCapabilityEndpoint
from eu.algites.frmw.aac.core.observation.dispatcher import AIcObservationDispatcher, AIcObservationSelector


def _register_object_schema(catalog, schema_id: str) -> None:
    resource = schema_id.replace(".", "-").replace("_", "-") + "_1.json"
    try:
        catalog.schema_registry.get_identity(schema_id, 1)
        return
    except KeyError:
        pass
    catalog.schema_registry.register(resource, {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-aac-schema-id": schema_id,
        "x-aac-schema-version": 1,
        "type": "object",
        "additionalProperties": True,
    })


def _object_operation(
    catalog, operation_id: str, *, prefix: str, input: bool = True, success: bool = True,
    running_complete: bool = False, running_delta: bool = False, cancelled: bool = False,
    sensitive_input_paths=(), sensitive_output_paths=(),
):
    interactions = []
    specs = (
        (input, AInCapabilityOperationInteractionKind.INPUT, "input"),
        (running_complete, AInCapabilityOperationInteractionKind.RUNNING_COMPLETE_STATE_RESULT, "running-complete"),
        (running_delta, AInCapabilityOperationInteractionKind.RUNNING_DELTA_STATE_RESULT, "running-delta"),
        (success, AInCapabilityOperationInteractionKind.FINAL_SUCCESS_STATE_RESULT, "success"),
        (cancelled, AInCapabilityOperationInteractionKind.FINAL_CANCELLED_STATE_RESULT, "cancelled"),
    )
    for enabled, kind, suffix in specs:
        if not enabled:
            continue
        schema_id = f"test.{prefix}.{suffix}"
        _register_object_schema(catalog, schema_id)
        interactions.append(AIcCapabilityOperationInteraction(kind, AIcSchemaRef(schema_id, 1)))
    return AIcCapabilityOperation(
        operation_id, tuple(interactions),
        sensitive_input_paths=tuple(sensitive_input_paths),
        sensitive_output_paths=tuple(sensitive_output_paths),
    )


class Echo:
    def run_1(self, token, value):
        return {"token": token, "value": value}


class Collector(AIiObservationProvider):
    def __init__(self):
        self.values = []
    def observe_1(self, observation_input):
        self.values.append(observation_input)
        return AIcObservationOutput()


def test_invocation_generates_pre_post_and_redacts_contract_sensitive_paths():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.admit(AIcCapabilityContract(
        AIcCapabilityRef("x.cap", 1),
        "_AAC.runtime",
        (_object_operation(catalog, "run", prefix="redaction", sensitive_input_paths=("token",), sensitive_output_paths=("token",)),),
    ))
    collector = Collector()
    observations = AIcObservationDispatcher()
    observations.register("observer", collector, (AIcObservationSelector(capability="x.cap"),))
    dispatcher = AIcInvocationDispatcher(catalog, observations)
    output = dispatcher.invoke(AIcObjectCapabilityEndpoint(Echo()), AIcInvocationInput(
        "inv", None, "x.cap", 1, "run", "provider", {"token": "secret", "value": 5}
    ))
    assert output.success and output.result["token"] == "secret"
    assert collector.values[0].arguments["token"] == "<redacted>"
    assert collector.values[1].result["token"] == "<redacted>"


def test_operation_input_and_output_schema_are_core_validated():
    from eu.algites.frmw.aac.core.capability.api import AIcCapabilityContract, AIcCapabilityOperation, AIcCapabilityRef
    from eu.algites.frmw.aac.core.invocation.api import AIcInvocationInput
    from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
    from eu.algites.frmw.aac.core.invocation.dispatcher import AIcInvocationDispatcher, AIcObjectCapabilityEndpoint
    from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry

    schemas = AIcSchemaRegistry()
    schemas.register("echo-input_1.json", {"x-aac-schema-id": "test.echo-input", "x-aac-schema-version": 1, "type": "object", "required": ["value"], "properties": {"value": {"type": "string"}}, "additionalProperties": False})
    schemas.register("echo-output_1.json", {"x-aac-schema-id": "test.echo-output", "x-aac-schema-version": 1, "type": "object", "required": ["value"], "properties": {"value": {"type": "string"}}, "additionalProperties": False})
    catalog = AIcActiveContractCatalog(schemas)
    catalog.admit_builtin_contracts()
    catalog.admit(AIcCapabilityContract(AIcCapabilityRef("test.schema", 1), "_AAC.runtime", (
        AIcCapabilityOperation("run", (
            AIcCapabilityOperationInteraction(AInCapabilityOperationInteractionKind.INPUT, AIcSchemaRef("test.echo-input", 1)),
            AIcCapabilityOperationInteraction(AInCapabilityOperationInteractionKind.FINAL_SUCCESS_STATE_RESULT, AIcSchemaRef("test.echo-output", 1)),
        )),
    )))

    class Provider:
        def run_1(self, value):
            return {"value": value}

    dispatcher = AIcInvocationDispatcher(catalog)
    bad = dispatcher.invoke(AIcObjectCapabilityEndpoint(Provider()), AIcInvocationInput("i1", None, "test.schema", 1, "run", "p", {"value": 7}))
    assert not bad.success and bad.error["type"] == "AIxSchemaValidationError"
    good = dispatcher.invoke(AIcObjectCapabilityEndpoint(Provider()), AIcInvocationInput("i2", None, "test.schema", 1, "run", "p", {"value": "ok"}))
    assert good.success and good.result == {"value": "ok"}


def test_permission_denied_is_normalized_for_core_bridge():
    from eu.algites.frmw.aac.core.entitlement.api import AInPermissionRetryDisposition
    from eu.algites.frmw.aac.core.errors import AIxPermissionDenied

    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.admit(AIcCapabilityContract(
        AIcCapabilityRef("x.secured", 1),
        "_AAC.runtime",
        (AIcCapabilityOperation("write"),),
    ))

    class Provider:
        def write_1(self):
            raise AIxPermissionDenied(
                "upgrade required",
                permission_id="WRITE",
                retry_disposition=AInPermissionRetryDisposition.SAFE_AFTER_ENTITLEMENT_CHANGE,
                remediation_hint="professional",
            )

    output = AIcInvocationDispatcher(catalog).invoke(
        AIcObjectCapabilityEndpoint(Provider()),
        AIcInvocationInput("i", None, "x.secured", 1, "write", "p", {}),
    )
    assert not output.success
    assert output.error["type"] == "PERMISSION_DENIED"
    assert output.error["permission_id"] == "WRITE"
    assert output.error["retry_disposition"] == "SAFE_AFTER_ENTITLEMENT_CHANGE"


def test_safe_permission_denial_can_remediate_refresh_and_retry_once():
    from eu.algites.frmw.aac.core.entitlement.api import (
        AInPermissionRetryDisposition, AIcEntitlementRemediationOutcome, AIiEntitlementRemediator,
    )
    from eu.algites.frmw.aac.core.errors import AIxPermissionDenied

    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.admit(AIcCapabilityContract(
        AIcCapabilityRef("x.remediate", 1),
        "_AAC.runtime",
        (AIcCapabilityOperation("write"),),
    ))

    class Provider:
        def __init__(self):
            self.calls = 0
        def write_1(self):
            self.calls += 1
            if self.calls == 1:
                raise AIxPermissionDenied(
                    "upgrade required", permission_id="WRITE",
                    retry_disposition=AInPermissionRetryDisposition.SAFE_AFTER_ENTITLEMENT_CHANGE,
                )
            return None

    class Remediator(AIiEntitlementRemediator):
        def __init__(self):
            self.calls = 0
        def remediate(self, request):
            self.calls += 1
            return AIcEntitlementRemediationOutcome(True)

    refreshed = []
    provider = Provider(); remediator = Remediator()
    dispatcher = AIcInvocationDispatcher(
        catalog, entitlement_remediator=remediator, entitlement_refresh_callback=lambda: refreshed.append(True)
    )
    output = dispatcher.invoke(
        AIcObjectCapabilityEndpoint(provider),
        AIcInvocationInput("i", None, "x.remediate", 1, "write", "provider-1", {}),
    )
    assert output.success and output.result is None
    assert provider.calls == 2 and remediator.calls == 1 and refreshed == [True]


def test_observation_contract_uses_direct_input_object_without_transport_wrapper():
    from dataclasses import asdict
    from eu.algites.frmw.aac.core.observation.api import AIcObservationInput, AInObservationPhase

    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()

    class EndpointObserver:
        def __init__(self):
            self.received = None

        def observe_1(self, observation_input: AIcObservationInput):
            self.received = observation_input
            return {"accepted": True}

    event = AIcObservationInput(
        invocation_id="observed",
        parent_invocation_id=None,
        phase=AInObservationPhase.PRE,
        capability_id="x.cap",
        capability_version=1,
        operation_id="run",
        provider_instance_id="provider",
        arguments={"value": 7},
    )
    provider = EndpointObserver()
    output = AIcInvocationDispatcher(catalog).invoke(
        AIcObjectCapabilityEndpoint(provider),
        AIcInvocationInput(
            "delivery", None, "_AAC.capability.observation", 1, "observe", "observer", asdict(event)
        ),
    )

    assert output.success and output.result["accepted"] is True
    assert isinstance(provider.received, AIcObservationInput)
    assert provider.received.invocation_id == "observed"
    assert provider.received.arguments == {"value": 7}

    wrapped = AIcInvocationDispatcher(catalog).invoke(
        AIcObjectCapabilityEndpoint(provider),
        AIcInvocationInput(
            "legacy", None, "_AAC.capability.observation", 1, "observe", "observer",
            {"observation_input": asdict(event)},
        ),
    )
    assert not wrapped.success
    assert wrapped.error["type"] == "AIxSchemaValidationError"


def test_effective_operation_parameters_are_separate_from_portable_input_and_visible_to_provider():
    from eu.algites.frmw.aac.core.invocation.api import current_operation_parameters

    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.admit(AIcCapabilityContract(
        AIcCapabilityRef("x.parameters", 1),
        "_AAC.runtime",
        (_object_operation(catalog, "run", prefix="object"),),
    ))

    class Provider:
        def run_1(self, value):
            return {"value": value, "parameters": dict(current_operation_parameters())}

    def resolve(invocation):
        assert invocation.arguments == {"value": 5}
        assert invocation.operation_parameter_overrides == {"strategy": "REBASE"}
        return {"strategy": "REBASE", "timeout": 30}

    dispatcher = AIcInvocationDispatcher(catalog, operation_parameter_resolver=resolve)
    output = dispatcher.invoke(
        AIcObjectCapabilityEndpoint(Provider()),
        AIcInvocationInput(
            "i", None, "x.parameters", 1, "run", "p", {"value": 5},
            operation_parameter_overrides={"strategy": "REBASE"},
        ),
    )
    assert output.success
    assert output.result == {"value": 5, "parameters": {"strategy": "REBASE", "timeout": 30}}


def test_operation_interaction_is_separate_from_portable_input_and_bidirectional():
    from eu.algites.frmw.aac.core.invocation.api import (
        AInOperationInteractionDetailLevel,
        AInOperationInteractionEventType,
        AInOperationInteractionMode,
        AIcOperationInteractionEvent,
        AIcOperationInteractionFeatures,
        current_operation_interaction,
    )
    from eu.algites.frmw.aac.core.presentation.api import AIcDisplayText
    from eu.algites.frmw.aac.core.interaction.controller import AIcOperationInteractionController

    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.admit(AIcCapabilityContract(
        AIcCapabilityRef("x.interaction", 1),
        "_AAC.runtime",
        (_object_operation(catalog, "run", prefix="object"),),
    ))

    class Provider:
        def run_1(self, value):
            interaction = current_operation_interaction()
            interaction.declare_features(AIcOperationInteractionFeatures(
                progress_reporting=True, cancellation=True, detail_level=True, reporting_interval=True,
            ))
            interaction.report(AIcOperationInteractionEvent(
                AInOperationInteractionEventType.PROGRESS,
                progress_id="work",
                phase_id="work",
                name=AIcDisplayText(text="Working"),
                current=2,
                total=4,
                unit="ITEMS",
            ))
            state = interaction.caller_snapshot()
            return {
                "value": value,
                "mode": state.interaction_mode.value,
                "detail": state.detail_level.value,
                "interval": state.reporting_interval_ms,
            }

    messages = []
    interaction = AIcOperationInteractionController(messages.append)
    interaction.declare_features(AIcOperationInteractionFeatures(
        progress_reporting=True, cancellation=True, detail_level=True, reporting_interval=True,
    ))
    interaction.set_interaction_mode(AInOperationInteractionMode.BACKGROUND)
    interaction.set_detail_level(AInOperationInteractionDetailLevel.DETAILED)
    interaction.set_reporting_interval_ms(750)
    messages.clear()
    output = AIcInvocationDispatcher(catalog).invoke(
        AIcObjectCapabilityEndpoint(Provider()),
        AIcInvocationInput("i", None, "x.interaction", 1, "run", "p", {"value": 5}),
        interaction,
    )
    assert output.success
    assert output.result == {"value": 5, "mode": "BACKGROUND", "detail": "DETAILED", "interval": 750}
    progress_events = [event for message in messages for event in message.events]
    assert len(progress_events) == 1
    assert progress_events[0].phase_id == "work" and progress_events[0].current == 2 and progress_events[0].total == 4
    assert interaction.provider_snapshot().features.progress_reporting is True


def test_async_start_uses_same_interaction_lifecycle_and_propagates_locale():
    from eu.algites.frmw.aac.core.capability.api import (
        AIcCapabilityContract,
        AIcCapabilityOperation,
        AIcCapabilityRef,
    )
    from eu.algites.frmw.aac.core.instances.api import AIcBinding
    from eu.algites.frmw.aac.core.invocation.api import (
        AInOperationExecutionState,
        AInStateResultDeliveryMode,
        AIcOperationInteractionFeatures,
        current_invocation_locale,
        current_operation_interaction,
    )
    from eu.algites.frmw.aac.core.interaction.controller import AIcOperationInteractionController
    from eu.algites.frmw.aac.core.invocation.dispatcher import AIcCoreCapabilityHandle, AIcEndpointRegistry

    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.admit(AIcCapabilityContract(
        AIcCapabilityRef("x.async", 1),
        "_AAC.runtime",
        (_object_operation(catalog, "run", prefix="async", running_delta=True),),
    ))

    class Provider:
        def run_1(self, value):
            interaction = current_operation_interaction()
            interaction.declare_features(AIcOperationInteractionFeatures(
                supported_state_result_delivery_modes=(
                    AInStateResultDeliveryMode.ON_DEMAND_COMPLETE,
                    AInStateResultDeliveryMode.ON_CHANGE_DELTA,
                ),
            ))
            interaction.update_state_result({"partial": value})
            return {"value": value, "locale": current_invocation_locale()}

    binding = AIcBinding("consumer", "requirement", "provider", "x.async", 1)
    endpoints = AIcEndpointRegistry()
    endpoints.register_object("provider", Provider())
    handle = AIcCoreCapabilityHandle(binding, endpoints, AIcInvocationDispatcher(catalog))
    messages = []
    interaction = AIcOperationInteractionController(messages.append)
    interaction.set_state_result_delivery_mode(AInStateResultDeliveryMode.ON_CHANGE_DELTA)

    returned = handle.start("run", {"value": 7}, operation_interaction=interaction, locale="cs-CZ")
    assert returned is interaction
    terminal = interaction.wait_for_terminal_state(timeout=2.0)

    assert terminal.execution_state is AInOperationExecutionState.COMPLETED
    assert terminal.state_result == {"value": 7, "locale": "cs-CZ"}
    assert terminal.state_result_revision == 2
    partial = [
        message for message in messages
        if message.execution_state is AInOperationExecutionState.RUNNING and message.state_result_included
    ]
    assert any(message.state_result == {"partial": 7} for message in partial)


def test_simple_synchronous_invocations_get_fresh_on_demand_interaction_state():
    from eu.algites.frmw.aac.core.capability.api import AIcCapabilityContract, AIcCapabilityOperation, AIcCapabilityRef
    from eu.algites.frmw.aac.core.invocation.api import current_operation_interaction

    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.admit(AIcCapabilityContract(
        AIcCapabilityRef("x.simple-interaction", 1),
        "_AAC.runtime",
        (_object_operation(catalog, "run", prefix="simple-interaction", input=False, running_complete=True),),
    ))

    class Provider:
        def run_1(self):
            interaction = current_operation_interaction()
            return {
                "mode": interaction.caller_snapshot().state_result_delivery_mode.value,
                "first_result_revision": interaction.update_state_result({"partial": True}),
            }

    dispatcher = AIcInvocationDispatcher(catalog)
    endpoint = AIcObjectCapabilityEndpoint(Provider())
    first = dispatcher.invoke(
        endpoint,
        AIcInvocationInput("i1", None, "x.simple-interaction", 1, "run", "p", {}),
    )
    second = dispatcher.invoke(
        endpoint,
        AIcInvocationInput("i2", None, "x.simple-interaction", 1, "run", "p", {}),
    )

    assert first.success and second.success
    assert first.result == {"mode": "ON_DEMAND_COMPLETE", "first_result_revision": 1}
    assert second.result == {"mode": "ON_DEMAND_COMPLETE", "first_result_revision": 1}


def test_cooperative_cancellation_can_publish_atomic_cancelled_state_result():
    from eu.algites.frmw.aac.core.capability.api import AIcCapabilityContract, AIcCapabilityOperation, AIcCapabilityRef
    from eu.algites.frmw.aac.core.invocation.api import (
        AInOperationExecutionState,
        AIxOperationCancelled,
    )
    from eu.algites.frmw.aac.core.interaction.controller import AIcOperationInteractionController

    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.admit(AIcCapabilityContract(
        AIcCapabilityRef("x.cancel-result", 1),
        "_AAC.runtime",
        (_object_operation(catalog, "run", prefix="cancel-result", input=False, success=False, cancelled=True),),
    ))

    class Provider:
        def run_1(self):
            raise AIxOperationCancelled(
                "cancelled after partial work",
                state_result={"processed": 7},
                has_state_result=True,
            )

    interaction = AIcOperationInteractionController()
    output = AIcInvocationDispatcher(catalog).invoke(
        AIcObjectCapabilityEndpoint(Provider()),
        AIcInvocationInput("cancel-i", None, "x.cancel-result", 1, "run", "p", {}),
        interaction,
    )

    assert not output.success
    terminal = interaction.provider_snapshot()
    assert terminal.execution_state is AInOperationExecutionState.CANCELLED
    assert terminal.state_result_revision == 1
    assert terminal.state_result_payload_revision == 1
    assert terminal.state_result == {"processed": 7}


def test_running_state_result_is_validated_against_selected_interaction_schema():
    from eu.algites.frmw.aac.core.capability.api import (
        AInCapabilityOperationInteractionKind,
        AIcCapabilityContract,
        AIcCapabilityOperation,
        AIcCapabilityOperationInteraction,
        AIcCapabilityRef,
        AIcSchemaRef,
    )
    from eu.algites.frmw.aac.core.invocation.api import (
        AInStateResultDeliveryMode,
        AIcOperationInteractionFeatures,
        current_operation_interaction,
    )
    from eu.algites.frmw.aac.core.interaction.controller import AIcOperationInteractionController

    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.schema_registry.register("stream-delta_1.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "x-aac-schema-id": "test.stream-delta",
        "x-aac-schema-version": 1,
        "type": "object",
        "required": ["chunk"],
        "properties": {"chunk": {"type": "string"}},
        "additionalProperties": False,
    })
    catalog.admit(AIcCapabilityContract(
        AIcCapabilityRef("test.running-validation", 1),
        "_AAC.runtime",
        (AIcCapabilityOperation("run", (
            AIcCapabilityOperationInteraction(
                AInCapabilityOperationInteractionKind.RUNNING_DELTA_STATE_RESULT,
                AIcSchemaRef("test.stream-delta", 1),
            ),
        )),),
    ))

    class Provider:
        def run_1(self):
            interaction = current_operation_interaction()
            interaction.declare_features(AIcOperationInteractionFeatures(
                supported_state_result_delivery_modes=(
                    AInStateResultDeliveryMode.ON_DEMAND_COMPLETE,
                    AInStateResultDeliveryMode.ON_CHANGE_DELTA,
                ),
            ))
            interaction.update_state_result({"chunk": 7})
            return None

    interaction = AIcOperationInteractionController()
    interaction.set_state_result_delivery_mode(AInStateResultDeliveryMode.ON_CHANGE_DELTA)
    output = AIcInvocationDispatcher(catalog).invoke(
        AIcObjectCapabilityEndpoint(Provider()),
        AIcInvocationInput("i", None, "test.running-validation", 1, "run", "p", {}),
        interaction,
    )
    assert not output.success
    assert str(output.error["type"]).endswith("AIxSchemaValidationError")
