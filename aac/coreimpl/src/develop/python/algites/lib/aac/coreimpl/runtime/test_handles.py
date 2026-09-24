from algites.lib.aac.coreintf.contracts import (
    AInCapabilityOperationInteractionKind, AIcCapabilityContract, AIcCapabilityOperation,
    AIcCapabilityOperationInteraction, AIcCapabilityRef, AIcSchemaRef,
)
from algites.lib.aac.coreintf.instances import AIcBinding
from algites.lib.aac.coreimpl.contracts import AIcActiveContractCatalog
from algites.lib.aac.coreimpl.invocation import AIcCapabilityHandleFactory, AIcEndpointRegistry, AIcInvocationDispatcher


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
