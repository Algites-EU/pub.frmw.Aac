from eu.algites.frmw.aac.core.capability.api import (
    AInCapabilityOperationInteractionKind, AIcCapabilityContract, AIcCapabilityOperation,
    AIcCapabilityOperationInteraction, AIcCapabilityRef, AIcSchemaRef,
)
from eu.algites.frmw.aac.core.instances.api import AIcBinding
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.invocation.dispatcher import AIcCapabilityHandleFactory, AIcEndpointRegistry, AIcInvocationDispatcher


class Echo:
    def ping_1(self, value):
        return {"value": value}


def test_core_capability_handle_invokes_bound_provider_instance():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.schema_registry.register("test-echo-input_1.json", {
        "x-aac-schema-id": "test.echo.input", "x-aac-schema-version": 1,
        "type": "object", "additionalProperties": True,
    })
    catalog.schema_registry.register("test-echo-output_1.json", {
        "x-aac-schema-id": "test.echo.output", "x-aac-schema-version": 1,
        "type": "object", "additionalProperties": True,
    })
    catalog.admit(AIcCapabilityContract(
        AIcCapabilityRef("test.echo", 1), "_AAC.runtime",
        (AIcCapabilityOperation("ping", (
            AIcCapabilityOperationInteraction(AInCapabilityOperationInteractionKind.INPUT, AIcSchemaRef("test.echo.input", 1)),
            AIcCapabilityOperationInteraction(AInCapabilityOperationInteractionKind.FINAL_SUCCESS_STATE_RESULT, AIcSchemaRef("test.echo.output", 1)),
        )),),
    ))
    endpoints = AIcEndpointRegistry(); endpoints.register_object("provider", Echo())
    handles = AIcCapabilityHandleFactory(endpoints, AIcInvocationDispatcher(catalog)).for_consumer(
        "consumer", (AIcBinding("consumer", "echo", "provider", "test.echo", 1),)
    )
    output = handles["echo"][0].invoke("ping", {"value": "ok"})
    assert output.success and output.result == {"value": "ok"}


def test_binding_qualifiers_are_available_in_operation_context():
    from eu.algites.frmw.aac.core.invocation.api import current_binding_qualifier_profiles

    class QualifiedEcho:
        def ping_1(self):
            return {"qualifiers": [dict(x) for x in current_binding_qualifier_profiles()]}

    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.schema_registry.register("test-qualified-output_1.json", {
        "x-aac-schema-id": "test.qualified.output", "x-aac-schema-version": 1,
        "type": "object", "additionalProperties": True,
    })
    catalog.admit(AIcCapabilityContract(
        AIcCapabilityRef("test.qualified-context", 1), "_AAC.runtime",
        (AIcCapabilityOperation("ping", (
            AIcCapabilityOperationInteraction(
                AInCapabilityOperationInteractionKind.FINAL_SUCCESS_STATE_RESULT,
                AIcSchemaRef("test.qualified.output", 1),
            ),
        )),),
    ))
    endpoints = AIcEndpointRegistry(); endpoints.register_object("provider", QualifiedEcho())
    binding = AIcBinding(
        "consumer", "qualified", "provider", "test.qualified-context", 1,
        {"TechnologyKind": "java", "BuildOutputType": "java-bin-jar"},
    )
    handle = AIcCapabilityHandleFactory(endpoints, AIcInvocationDispatcher(catalog)).for_consumer(
        "consumer", (binding,)
    )["qualified"][0]
    output = handle.invoke("ping")
    assert output.success
    assert output.result == {"qualifiers": {"TechnologyKind": "java", "BuildOutputType": "java-bin-jar"}}
