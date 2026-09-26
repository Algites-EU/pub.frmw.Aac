from abc import ABC
from typing import Mapping

import pytest

from eu.algites.frmw.aac.core.capability.api import AIcProvidedCapability
from eu.algites.frmw.aac.core.dataentity.api import (
    AIcDataEntityImplementationBinding,
    AIcDataEntityType,
    AIcDataEntityViewBinding,
    AIiDataEntityCodec,
    AIiDataEntityView,
)
from eu.algites.frmw.aac.core.instances.api import AIcProviderInstance, AInProviderAccessMode
from eu.algites.frmw.aac.core.invocation.api import AIcInvocationInput
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.dataentity.runtime import (
    APPLY_DIRECT_RECORD_CHANGES_CAPABILITY_ID,
    GET_RECORD_CAPABILITY_ID,
    AIcDataEntityImplementationRegistry,
    AIcDataEntityMarshaller,
    AIcDataEntityProviderFacade,
    AIcDataEntityViewRegistry,
)
from eu.algites.frmw.aac.core.invocation.dispatcher import AIcEndpointRegistry, AIcInvocationDispatcher, AIcObjectCapabilityEndpoint
from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry


class E1_1(AIiDataEntityView, ABC):
    def get_name_1(self) -> str: ...
    def set_name_1(self, value: str) -> None: ...


class E1_2(AIiDataEntityView, ABC):
    def get_name_2(self) -> str: ...
    def set_name_2(self, value: str) -> None: ...
    def get_currency_2(self) -> str: ...
    def set_currency_2(self, value: str) -> None: ...


E1_TYPE_1 = AIcDataEntityType("test.e1", 1, E1_1)
E1_TYPE_2 = AIcDataEntityType("test.e1", 2, E1_2)


class E1(E1_1, E1_2):
    def __init__(self) -> None:
        self.name = ""
        self.currency = "CZK"

    def get_name_1(self) -> str:
        return self.name

    def set_name_1(self, value: str) -> None:
        self.name = value

    def get_name_2(self) -> str:
        return self.name

    def set_name_2(self, value: str) -> None:
        self.name = value

    def get_currency_2(self) -> str:
        return self.currency

    def set_currency_2(self, value: str) -> None:
        self.currency = value


class Codec1(AIiDataEntityCodec[E1_1]):
    schema_id = "test.e1"
    schema_version = 1
    view_type = E1_1

    def serialize(self, value: E1_1) -> Mapping[str, object]:
        return {"Name": value.get_name_1()}

    def deserialize_into(self, payload: Mapping[str, object], target: E1_1) -> None:
        target.set_name_1(str(payload["Name"]))


class Codec2(AIiDataEntityCodec[E1_2]):
    schema_id = "test.e1"
    schema_version = 2
    view_type = E1_2

    def serialize(self, value: E1_2) -> Mapping[str, object]:
        return {"Name": value.get_name_2(), "Currency": value.get_currency_2()}

    def deserialize_into(self, payload: Mapping[str, object], target: E1_2) -> None:
        target.set_name_2(str(payload["Name"]))
        target.set_currency_2(str(payload["Currency"]))


class StorageProvider:
    def __init__(self) -> None:
        self.applied = None

    def get_1(self, request):
        assert request == {"SchemaId": "test.e1", "Uid": "u1"}
        return {
            "Record": {
                "Uid": "u1",
                "SchemaId": "test.e1",
                "SchemaVersion": 1,
                "RecordRevision": 7,
                "State": "active",
                "Payload": {"Name": "old"},
            }
        }

    def apply_1(self, request):
        self.applied = request
        change = request["Changes"][0]
        return {
            "Changes": [{
                "ChangeId": change["ChangeId"],
                "Type": change["Type"],
                "SchemaId": change["SchemaId"],
                "Uid": change["Uid"],
                "RecordRevision": 8,
            }]
        }


def _marshaller() -> AIcDataEntityMarshaller:
    schemas = AIcSchemaRegistry()
    for version, required, properties in (
        (1, ["Name"], {"Name": {"type": "string"}}),
        (2, ["Name", "Currency"], {"Name": {"type": "string"}, "Currency": {"type": "string"}}),
    ):
        schemas.register(f"test-e1_{version}.json", {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "x-aac-schema-id": "test.e1",
            "x-aac-schema-version": version,
            "type": "object",
            "required": required,
            "additionalProperties": False,
            "properties": properties,
        })
    views = AIcDataEntityViewRegistry()
    views.register(AIcDataEntityViewBinding(E1_TYPE_1, Codec1()))
    views.register(AIcDataEntityViewBinding(E1_TYPE_2, Codec2()))
    implementations = AIcDataEntityImplementationRegistry()
    implementations.register(AIcDataEntityImplementationBinding(
        "test.e1", 2, E1, E1, (1, 2)
    ))
    result = AIcDataEntityMarshaller(schemas, views, implementations)
    result.validate_registrations("test.e1")
    return result


def _facade(mode=AInProviderAccessMode.READ_WRITE):
    catalog = AIcActiveContractCatalog()
    catalog.admit_builtin_contracts()
    dispatcher = AIcInvocationDispatcher(catalog)
    endpoints = AIcEndpointRegistry()
    runtime = StorageProvider()
    provider = AIcProviderInstance(
        "storage", "component", "storage", "storage",
        (
            AIcProvidedCapability(GET_RECORD_CAPABILITY_ID, (1,)),
            AIcProvidedCapability(APPLY_DIRECT_RECORD_CHANGES_CAPABILITY_ID, (1,)),
        ),
        "test:StorageProvider",
        access_mode=mode,
    )
    endpoints.register_object(provider.id, runtime)
    return AIcDataEntityProviderFacade(provider, endpoints, dispatcher, _marshaller()), runtime


def test_stored_v1_materializes_as_current_polymorphic_v2_and_saves_canonical_v2():
    facade, runtime = _facade()
    envelope = facade.get_record.get(E1_TYPE_2, "u1")
    assert envelope is not None
    assert envelope.stored_schema_version == 1
    assert envelope.canonical_schema_version == 2
    assert isinstance(envelope.entity, E1_1)
    assert isinstance(envelope.entity, E1_2)
    assert envelope.entity.get_name_2() == "old"
    assert envelope.entity.get_currency_2() == "CZK"

    envelope.entity.set_name_2("new")
    envelope.entity.set_currency_2("EUR")
    facade.apply_changes.save(envelope)
    change = runtime.applied["Changes"][0]
    assert change["SchemaVersion"] == 2
    assert change["Payload"] == {"Name": "new", "Currency": "EUR"}
    assert change["ExpectedRecordRevision"] == 7


def test_read_only_provider_can_read_but_write_facade_rejects_mutation():
    facade, _ = _facade(AInProviderAccessMode.READ_ONLY)
    envelope = facade.get_record.get(E1_TYPE_2, "u1")
    assert envelope is not None
    with pytest.raises(PermissionError, match="read_only"):
        facade.apply_changes.save(envelope)


def test_generated_invoker_selection_is_capability_specific_for_multiple_interfaces():
    class A:
        __aac_capability_id__ = "test.a"
        __aac_capability_version__ = 1
        def __aac_invoke__(self, operation_id, arguments):
            return {"selected": "a"}

    class B:
        __aac_capability_id__ = "test.b"
        __aac_capability_version__ = 1
        def __aac_invoke__(self, operation_id, arguments):
            return {"selected": "b"}

    class Multi(A, B):
        pass

    endpoint = AIcObjectCapabilityEndpoint(Multi())
    output = endpoint.invoke(AIcInvocationInput("i", None, "test.b", 1, "run", "p", {}))
    assert output.success
    assert output.result == {"selected": "b"}
