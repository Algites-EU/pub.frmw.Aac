from algites.lib.aac.coreintf.contracts import AIcCapabilityContract, AIcCapabilityOperation, AIcCapabilityRef
from algites.lib.aac.coreintf.invocation import AIcInvocationInput
from algites.lib.aac.coreintf.observation import AIcObservationOutput, AIiObservationProvider
from algites.lib.aac.coreimpl.contracts import AIcActiveContractCatalog
from algites.lib.aac.coreimpl.invocation import AIcInvocationDispatcher, AIcObjectCapabilityEndpoint
from algites.lib.aac.coreimpl.observation import AIcObservationDispatcher, AIcObservationSelector


class Echo:
    def run(self, token, value):
        return {"token": token, "value": value}


class Collector(AIiObservationProvider):
    def __init__(self):
        self.values = []
    def observe(self, observation_input):
        self.values.append(observation_input)
        return AIcObservationOutput()


def test_invocation_generates_pre_post_and_redacts_contract_sensitive_paths():
    catalog = AIcActiveContractCatalog()
    catalog.admit(AIcCapabilityContract(
        AIcCapabilityRef("x.cap", 1),
        (AIcCapabilityOperation("run", "In", "Out", sensitive_input_paths=("token",), sensitive_output_paths=("token",)),),
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
    from algites.lib.aac.coreintf.contracts import AIcCapabilityContract, AIcCapabilityOperation, AIcCapabilityRef
    from algites.lib.aac.coreintf.invocation import AIcInvocationInput
    from algites.lib.aac.coreimpl.contracts import AIcActiveContractCatalog
    from algites.lib.aac.coreimpl.invocation import AIcInvocationDispatcher, AIcObjectCapabilityEndpoint
    from algites.lib.aac.coreimpl.schemas import AIcSchemaRegistry

    schemas = AIcSchemaRegistry()
    schemas.register("echo-input_1.json", {"type": "object", "required": ["value"], "properties": {"value": {"type": "string"}}, "additionalProperties": False})
    schemas.register("echo-output_1.json", {"type": "object", "required": ["value"], "properties": {"value": {"type": "string"}}, "additionalProperties": False})
    catalog = AIcActiveContractCatalog(schemas)
    catalog.admit(AIcCapabilityContract(AIcCapabilityRef("test.schema", 1), (
        AIcCapabilityOperation("run", "Input", "Output", input_schema="echo-input_1.json", output_schema="echo-output_1.json"),
    )))

    class Provider:
        def run(self, value):
            return {"value": value}

    dispatcher = AIcInvocationDispatcher(catalog)
    bad = dispatcher.invoke(AIcObjectCapabilityEndpoint(Provider()), AIcInvocationInput("i1", None, "test.schema", 1, "run", "p", {"value": 7}))
    assert not bad.success and bad.error["type"] == "AIxSchemaValidationError"
    good = dispatcher.invoke(AIcObjectCapabilityEndpoint(Provider()), AIcInvocationInput("i2", None, "test.schema", 1, "run", "p", {"value": "ok"}))
    assert good.success and good.result == {"value": "ok"}


def test_permission_denied_is_normalized_for_core_bridge():
    from algites.lib.aac.coreintf.entitlement import AInPermissionRetryDisposition
    from algites.lib.aac.coreintf.errors import AIxPermissionDenied

    catalog = AIcActiveContractCatalog()
    catalog.admit(AIcCapabilityContract(
        AIcCapabilityRef("x.secured", 1),
        (AIcCapabilityOperation("write", "In", "Out"),),
    ))

    class Provider:
        def write(self):
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
    from algites.lib.aac.coreintf.entitlement import (
        AInPermissionRetryDisposition, AIcEntitlementRemediationOutcome, AIiEntitlementRemediator,
    )
    from algites.lib.aac.coreintf.errors import AIxPermissionDenied

    catalog = AIcActiveContractCatalog()
    catalog.admit(AIcCapabilityContract(
        AIcCapabilityRef("x.remediate", 1),
        (AIcCapabilityOperation("write", "In", "Out"),),
    ))

    class Provider:
        def __init__(self):
            self.calls = 0
        def write(self):
            self.calls += 1
            if self.calls == 1:
                raise AIxPermissionDenied(
                    "upgrade required", permission_id="WRITE",
                    retry_disposition=AInPermissionRetryDisposition.SAFE_AFTER_ENTITLEMENT_CHANGE,
                )
            return {"ok": True}

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
    assert output.success and output.result == {"ok": True}
    assert provider.calls == 2 and remediator.calls == 1 and refreshed == [True]
