from abc import ABC
from typing import Mapping

import pytest

from algites.lib.aac.coreintf.contracts import AIcProvidedCapability
from algites.lib.aac.coreintf.dataentity import (
    AIcDataEntityImplementationBinding,
    AIcDataEntityType,
    AIcDataEntityViewBinding,
    AIiDataEntityCodec,
    AIiDataEntityView,
)
from algites.lib.aac.coreintf.instances import AIcProviderInstance, AInProviderAccessMode
from algites.lib.aac.coreintf.invocation import AIcInvocationInput
from algites.lib.aac.coreimpl.contracts import AIcActiveContractCatalog
from algites.lib.aac.coreimpl.dataentity import (
    APPLY_DIRECT_RECORD_CHANGES_CAPABILITY_ID,
    GET_RECORD_CAPABILITY_ID,
    AIcDataEntityImplementationRegistry,
    AIcDataEntityMarshaller,
    AIcDataEntityProviderFacade,
    AIcDataEntityViewRegistry,
)
from algites.lib.aac.coreimpl.invocation import AIcEndpointRegistry, AIcInvocationDispatcher, AIcObjectCapabilityEndpoint
from algites.lib.aac.coreimpl.schemas import AIcSchemaRegistry


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
        return {"name": value.get_name_1()}

    def deserialize_into(self, payload: Mapping[str, object], target: E1_1) -> None:
        target.set_name_1(str(payload["name"]))


class Codec2(AIiDataEntityCodec[E1_2]):
    schema_id = "test.e1"
    schema_version = 2
    view_type = E1_2

    def serialize(self, value: E1_2) -> Mapping[str, object]:
        return {"name": value.get_name_2(), "currency": value.get_currency_2()}

    def deserialize_into(self, payload: Mapping[str, object], target: E1_2) -> None:
        target.set_name_2(str(payload["name"]))
        target.set_currency_2(str(payload["currency"]))


class StorageProvider:
    def __init__(self) -> None:
        self.applied = None

    def get_1(self, request):
        assert request == {"schema_id": "test.e1", "uid": "u1"}
        return {
            "record": {
                "uid": "u1",
                "schema_id": "test.e1",
                "schema_version": 1,
                "record_revision": 7,
                "state": "ACTIVE",
                "payload": {"name": "old"},
            }
        }

    def apply_1(self, request):
        self.applied = request
        change = request["changes"][0]
        return {
            "changes": [{
                "change_id": change["change_id"],
                "type": change["type"],
                "schema_id": change["schema_id"],
                "uid": change["uid"],
                "record_revision": 8,
            }]
        }


def _marshaller() -> AIcDataEntityMarshaller:
    schemas = AIcSchemaRegistry()
    for version, required, properties in (
        (1, ["name"], {"name": {"type": "string"}}),
        (2, ["name", "currency"], {"name": {"type": "string"}, "currency": {"type": "string"}}),
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
    change = runtime.applied["changes"][0]
    assert change["schema_version"] == 2
    assert change["payload"] == {"name": "new", "currency": "EUR"}
    assert change["expected_record_revision"] == 7


def test_read_only_provider_can_read_but_write_facade_rejects_mutation():
    facade, _ = _facade(AInProviderAccessMode.READ_ONLY)
    envelope = facade.get_record.get(E1_TYPE_2, "u1")
    assert envelope is not None
    with pytest.raises(PermissionError, match="READ_ONLY"):
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
