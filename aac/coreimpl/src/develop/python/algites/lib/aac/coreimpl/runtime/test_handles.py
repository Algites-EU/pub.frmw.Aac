from algites.lib.aac.coreintf.contracts import AIcCapabilityContract, AIcCapabilityOperation, AIcCapabilityRef
from algites.lib.aac.coreintf.instances import AIcBinding
from algites.lib.aac.coreimpl.contracts import AIcActiveContractCatalog
from algites.lib.aac.coreimpl.invocation import AIcCapabilityHandleFactory, AIcEndpointRegistry, AIcInvocationDispatcher


class Echo:
    def ping_1(self, value):
        return {"value": value}


def test_core_capability_handle_invokes_bound_provider_instance():
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    catalog.admit(AIcCapabilityContract(AIcCapabilityRef("test.echo", 1), "_AAC.runtime", (AIcCapabilityOperation("ping", "Input", "Output"),)))
    endpoints = AIcEndpointRegistry(); endpoints.register_object("provider", Echo())
    handles = AIcCapabilityHandleFactory(endpoints, AIcInvocationDispatcher(catalog)).for_consumer(
        "consumer", (AIcBinding("consumer", "echo", "provider", "test.echo", 1),)
    )
    output = handles["echo"][0].invoke("ping", {"value": "ok"})
    assert output.success and output.result == {"value": "ok"}
