from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Mapping, TypeVar
from uuid import uuid4

from algites.lib.aac.coreintf.dataentity import (
    AIcDataEntityEnvelope,
    AIcDataEntityImplementationBinding,
    AIcDataEntityType,
    AIcDataEntityViewBinding,
    AIcTypedDataEntityEnvelope,
    AInDataEntityState,
)
from algites.lib.aac.coreintf.instances import AIcProviderInstance, AInProviderAccessMode
from algites.lib.aac.coreintf.invocation import AIcInvocationInput

from .contracts import AIcActiveContractCatalog
from .invocation import AIcEndpointRegistry, AIcInvocationDispatcher
from .schemas import AIcSchemaRegistry


T = TypeVar("T")

GET_RECORD_CAPABILITY_ID = "_AAC.data-entity.get-record"
QUERY_RECORDS_CAPABILITY_ID = "_AAC.data-entity.query-records"
APPLY_DIRECT_RECORD_CHANGES_CAPABILITY_ID = "_AAC.data-entity.apply-direct-record-changes"
INSPECT_STORAGE_SUPPORT_CAPABILITY_ID = "_AAC.data-entity.inspect-storage-support"
ENSURE_STORAGE_SUPPORT_CAPABILITY_ID = "_AAC.data-entity.ensure-storage-support"
RETIRE_STORAGE_SUPPORT_CAPABILITY_ID = "_AAC.data-entity.retire-storage-support"
CREATE_STORAGE_BACKUP_CAPABILITY_ID = "_AAC.data-entity.create-storage-backup"
INSPECT_STORAGE_BACKUP_CAPABILITY_ID = "_AAC.data-entity.inspect-storage-backup"
RESTORE_STORAGE_BACKUP_CAPABILITY_ID = "_AAC.data-entity.restore-storage-backup"


class AIcDataEntityViewRegistry:
    def __init__(self) -> None:
        self._bindings: dict[tuple[str, int], AIcDataEntityViewBinding[object]] = {}
        self._by_interface: dict[type[object], AIcDataEntityViewBinding[object]] = {}

    def register(self, binding: AIcDataEntityViewBinding[object]) -> None:
        key = (binding.data_type.schema_id, binding.data_type.view_version)
        existing = self._bindings.get(key)
        if existing is not None and existing != binding:
            raise ValueError(f"conflicting data entity view binding for {key[0]}/{key[1]}")
        interface_existing = self._by_interface.get(binding.data_type.interface_type)
        if interface_existing is not None and interface_existing.data_type != binding.data_type:
            raise ValueError("data entity view interface is already registered for another schema/version")
        self._bindings[key] = binding
        self._by_interface[binding.data_type.interface_type] = binding

    def get(self, schema_id: str, version: int) -> AIcDataEntityViewBinding[object]:
        return self._bindings[(schema_id, version)]

    def for_type(self, data_type: AIcDataEntityType[T]) -> AIcDataEntityViewBinding[T]:
        binding = self.get(data_type.schema_id, data_type.view_version)
        if binding.data_type.interface_type is not data_type.interface_type:
            raise TypeError("registered Data Entity view interface differs from requested DataEntityType")
        return binding  # type: ignore[return-value]


class AIcDataEntityImplementationRegistry:
    def __init__(self) -> None:
        self._bindings: dict[str, AIcDataEntityImplementationBinding] = {}
        self._by_type: dict[type[object], AIcDataEntityImplementationBinding] = {}

    def register(self, binding: AIcDataEntityImplementationBinding) -> None:
        existing = self._bindings.get(binding.schema_id)
        if existing is not None and existing != binding:
            raise ValueError(f"conflicting Data Entity implementation for {binding.schema_id!r}")
        type_existing = self._by_type.get(binding.implementation_type)
        if type_existing is not None and type_existing.schema_id != binding.schema_id:
            raise ValueError("Data Entity implementation class is already registered for another schema")
        self._bindings[binding.schema_id] = binding
        self._by_type[binding.implementation_type] = binding

    def get(self, schema_id: str) -> AIcDataEntityImplementationBinding:
        return self._bindings[schema_id]

    def for_object(self, value: object) -> AIcDataEntityImplementationBinding:
        for implementation_type, binding in self._by_type.items():
            if isinstance(value, implementation_type):
                return binding
        raise KeyError(type(value))


class AIcDataEntityMarshaller:
    """Bridge canonical JSON envelopes and current polymorphic implementation objects."""

    def __init__(
        self,
        schemas: AIcSchemaRegistry,
        views: AIcDataEntityViewRegistry | None = None,
        implementations: AIcDataEntityImplementationRegistry | None = None,
    ) -> None:
        self.schemas = schemas
        self.views = views or AIcDataEntityViewRegistry()
        self.implementations = implementations or AIcDataEntityImplementationRegistry()

    def validate_registrations(self, schema_id: str) -> None:
        implementation = self.implementations.get(schema_id)
        if not self.schemas.contains_identity(schema_id, implementation.canonical_schema_version):
            raise ValueError(
                f"canonical schema {schema_id}/{implementation.canonical_schema_version} is not registered"
            )
        for version in implementation.supported_view_versions:
            view = self.views.get(schema_id, version)
            if not issubclass(implementation.implementation_type, view.data_type.interface_type):
                raise TypeError(
                    f"implementation {implementation.implementation_type.__qualname__} does not implement "
                    f"registered view {schema_id}/{version}"
                )

    def materialize(
        self,
        envelope: AIcDataEntityEnvelope,
        requested_type: AIcDataEntityType[T],
    ) -> AIcTypedDataEntityEnvelope[T]:
        if requested_type.schema_id != envelope.schema_id:
            raise ValueError("requested Data Entity type does not match stored schema id")
        implementation = self.implementations.get(envelope.schema_id)
        if requested_type.view_version not in implementation.supported_view_versions:
            raise TypeError(
                f"current implementation of {envelope.schema_id!r} does not support view {requested_type.view_version}"
            )
        stored_view = self.views.get(envelope.schema_id, envelope.schema_version)
        if envelope.schema_version not in implementation.supported_view_versions:
            raise TypeError(
                f"stored {envelope.schema_id}/{envelope.schema_version} cannot be loaded because the current "
                "implementation no longer supports that persistence view; migrate stored records first"
            )
        self.schemas.normalize_value(
            self.schemas.get_identity(envelope.schema_id, envelope.schema_version).resource_name,
            envelope.payload,
            apply_defaults=False,
        )
        target = implementation.factory()
        if not isinstance(target, implementation.implementation_type):
            raise TypeError("Data Entity implementation factory returned the wrong type")
        if not isinstance(target, stored_view.data_type.interface_type):
            raise TypeError("current implementation does not implement the stored schema view")
        stored_view.codec.deserialize_into(envelope.payload, target)
        requested_binding = self.views.for_type(requested_type)
        if not isinstance(target, requested_binding.data_type.interface_type):
            raise TypeError("current implementation does not implement the requested Data Entity view")
        return AIcTypedDataEntityEnvelope(
            uid=envelope.uid,
            schema_id=envelope.schema_id,
            stored_schema_version=envelope.schema_version,
            canonical_schema_version=implementation.canonical_schema_version,
            record_revision=envelope.record_revision,
            state=envelope.state,
            entity=target,
        )

    def marshal(self, envelope: AIcTypedDataEntityEnvelope[object]) -> AIcDataEntityEnvelope:
        implementation = self.implementations.get(envelope.schema_id)
        if not isinstance(envelope.entity, implementation.implementation_type):
            raise TypeError("typed Data Entity envelope contains an unregistered implementation object")
        canonical_view = self.views.get(envelope.schema_id, implementation.canonical_schema_version)
        if not isinstance(envelope.entity, canonical_view.data_type.interface_type):
            raise TypeError("Data Entity implementation does not implement its canonical view")
        payload = dict(canonical_view.codec.serialize(envelope.entity))
        normalized = self.schemas.normalize_value(
            self.schemas.get_identity(envelope.schema_id, implementation.canonical_schema_version).resource_name,
            payload,
            apply_defaults=False,
        )
        if not isinstance(normalized, Mapping):
            raise TypeError("canonical Data Entity schema must normalize to a JSON object")
        return AIcDataEntityEnvelope(
            uid=envelope.uid,
            schema_id=envelope.schema_id,
            schema_version=implementation.canonical_schema_version,
            record_revision=envelope.record_revision,
            state=envelope.state,
            payload=dict(normalized),
        )


class AIcProviderCapabilityInvoker:
    """Invoke one capability on one explicitly selected provider instance."""

    def __init__(
        self,
        provider: AIcProviderInstance,
        endpoints: AIcEndpointRegistry,
        dispatcher: AIcInvocationDispatcher,
    ) -> None:
        self.provider = provider
        self.endpoints = endpoints
        self.dispatcher = dispatcher

    def invoke(self, capability_id: str, version: int, operation_id: str, arguments: Mapping[str, object]) -> Mapping[str, object]:
        capability = self.provider.capability(capability_id)
        if version not in capability.versions:
            raise ValueError(
                f"provider {self.provider.id!r} does not provide {capability_id}/{version}"
            )
        invocation = AIcInvocationInput(
            invocation_id=str(uuid4()),
            parent_invocation_id=None,
            capability_id=capability_id,
            capability_version=version,
            operation_id=operation_id,
            provider_instance_id=self.provider.id,
            arguments=dict(arguments),
        )
        output = self.dispatcher.invoke(self.endpoints.get(self.provider.id), invocation)
        if not output.success:
            raise RuntimeError(f"provider capability invocation failed: {output.error}")
        if not isinstance(output.result, Mapping):
            raise TypeError("Data Entity provider operation returned a non-object result")
        return dict(output.result)


class AIcBoundDataEntityCapabilityFacade:
    capability_id: str
    capability_version = 1
    write_operation = False

    def __init__(self, invoker: AIcProviderCapabilityInvoker, marshaller: AIcDataEntityMarshaller | None = None) -> None:
        self.invoker = invoker
        self.marshaller = marshaller

    def _invoke(self, operation_id: str, arguments: Mapping[str, object]) -> Mapping[str, object]:
        if self.write_operation and self.invoker.provider.access_mode is AInProviderAccessMode.READ_ONLY:
            raise PermissionError(
                f"provider instance {self.invoker.provider.id!r} is configured READ_ONLY"
            )
        return self.invoker.invoke(self.capability_id, self.capability_version, operation_id, arguments)


class AIcGetRecordFacade(AIcBoundDataEntityCapabilityFacade):
    capability_id = GET_RECORD_CAPABILITY_ID

    def get_raw(self, schema_id: str, uid: str) -> AIcDataEntityEnvelope | None:
        result = self._invoke("get", {"schema_id": schema_id, "uid": uid})
        raw = result.get("record")
        return None if raw is None else _raw_envelope(raw)

    def get(self, data_type: AIcDataEntityType[T], uid: str) -> AIcTypedDataEntityEnvelope[T] | None:
        if self.marshaller is None:
            raise RuntimeError("typed Data Entity access requires a marshaller")
        raw = self.get_raw(data_type.schema_id, uid)
        return None if raw is None else self.marshaller.materialize(raw, data_type)


@dataclass(frozen=True, slots=True)
class AIcDataEntityQueryPage(Generic[T]):
    records: tuple[AIcTypedDataEntityEnvelope[T], ...]
    continuation_token: str | None


class AIcQueryRecordsFacade(AIcBoundDataEntityCapabilityFacade):
    capability_id = QUERY_RECORDS_CAPABILITY_ID

    def query_raw(self, request: Mapping[str, object]) -> tuple[tuple[AIcDataEntityEnvelope, ...], str | None]:
        result = self._invoke("query", request)
        records = tuple(_raw_envelope(item) for item in result.get("records", ()))
        token = result.get("continuation_token")
        return records, str(token) if token is not None else None

    def query(
        self,
        data_type: AIcDataEntityType[T],
        *,
        stored_schema_version_filter: tuple[int, ...] = (),
        states: tuple[AInDataEntityState, ...] = (AInDataEntityState.ACTIVE,),
        uids: tuple[str, ...] = (),
        limit: int = 100,
        continuation_token: str | None = None,
    ) -> AIcDataEntityQueryPage[T]:
        request: dict[str, object] = {
            "schema_id": data_type.schema_id,
            "states": [state.value for state in states],
            "limit": limit,
        }
        if stored_schema_version_filter:
            request["stored_schema_version_filter"] = list(stored_schema_version_filter)
        if uids:
            request["uids"] = list(uids)
        if continuation_token is not None:
            request["continuation_token"] = continuation_token
        if self.marshaller is None:
            raise RuntimeError("typed Data Entity access requires a marshaller")
        records, token = self.query_raw(request)
        return AIcDataEntityQueryPage(
            tuple(self.marshaller.materialize(record, data_type) for record in records), token
        )


class AIcApplyDirectRecordChangesFacade(AIcBoundDataEntityCapabilityFacade):
    capability_id = APPLY_DIRECT_RECORD_CHANGES_CAPABILITY_ID
    write_operation = True

    def apply_raw(self, changes: tuple[Mapping[str, object], ...]) -> Mapping[str, object]:
        return self._invoke("apply", {"changes": [dict(change) for change in changes]})

    def save(self, envelope: AIcTypedDataEntityEnvelope[object]) -> Mapping[str, object]:
        if self.marshaller is None:
            raise RuntimeError("typed Data Entity access requires a marshaller")
        raw = self.marshaller.marshal(envelope)
        result = self.apply_raw(({
            "change_id": str(uuid4()),
            "type": "REPLACE_RECORD",
            "schema_id": raw.schema_id,
            "uid": raw.uid,
            "schema_version": raw.schema_version,
            "state": raw.state.value,
            "payload": dict(raw.payload),
            "expected_record_revision": raw.record_revision,
        },))
        return result

    def create(
        self,
        schema_id: str,
        uid: str,
        entity: object,
        *,
        state: AInDataEntityState = AInDataEntityState.ACTIVE,
    ) -> Mapping[str, object]:
        if self.marshaller is None:
            raise RuntimeError("typed Data Entity access requires a marshaller")
        implementation = self.marshaller.implementations.get(schema_id)
        if not isinstance(entity, implementation.implementation_type):
            raise TypeError("create entity does not match the registered Data Entity implementation")
        canonical_view = self.marshaller.views.get(schema_id, implementation.canonical_schema_version)
        payload = dict(canonical_view.codec.serialize(entity))
        normalized = self.marshaller.schemas.normalize_value(
            self.marshaller.schemas.get_identity(schema_id, implementation.canonical_schema_version).resource_name,
            payload,
            apply_defaults=False,
        )
        if not isinstance(normalized, Mapping):
            raise TypeError("canonical Data Entity schema must normalize to a JSON object")
        payload = dict(normalized)
        return self.apply_raw(({
            "change_id": str(uuid4()),
            "type": "CREATE_RECORD",
            "schema_id": schema_id,
            "uid": uid,
            "schema_version": implementation.canonical_schema_version,
            "state": state.value,
            "payload": payload,
        },))

    def delete(self, schema_id: str, uid: str, expected_record_revision: int | str) -> Mapping[str, object]:
        return self.apply_raw(({
            "change_id": str(uuid4()),
            "type": "DELETE_RECORD",
            "schema_id": schema_id,
            "uid": uid,
            "expected_record_revision": expected_record_revision,
        },))


class AIcInspectStorageSupportFacade(AIcBoundDataEntityCapabilityFacade):
    capability_id = INSPECT_STORAGE_SUPPORT_CAPABILITY_ID

    def inspect(self, schema_id: str, schema_version: int) -> Mapping[str, object]:
        return self._invoke("inspect", {"schema_id": schema_id, "schema_version": schema_version})


class AIcEnsureStorageSupportFacade(AIcBoundDataEntityCapabilityFacade):
    capability_id = ENSURE_STORAGE_SUPPORT_CAPABILITY_ID
    write_operation = True

    def ensure(self, schema_id: str, schema_version: int, canonical_schema: Mapping[str, object], references=()) -> Mapping[str, object]:
        return self._invoke("ensure", {
            "schema_id": schema_id,
            "schema_version": schema_version,
            "canonical_schema": dict(canonical_schema),
            "references": list(references),
        })


class AIcRetireStorageSupportFacade(AIcBoundDataEntityCapabilityFacade):
    capability_id = RETIRE_STORAGE_SUPPORT_CAPABILITY_ID
    write_operation = True

    def retire(self, schema_id: str, schema_version: int) -> Mapping[str, object]:
        return self._invoke("retire", {"schema_id": schema_id, "schema_version": schema_version})


class AIcCreateStorageBackupFacade(AIcBoundDataEntityCapabilityFacade):
    capability_id = CREATE_STORAGE_BACKUP_CAPABILITY_ID

    def create_backup(self, backup_file: str, *, overwrite: bool = False) -> Mapping[str, object]:
        arguments: dict[str, object] = {"backup_file": backup_file}
        if overwrite:
            arguments["overwrite"] = True
        return self._invoke("create_backup", arguments)


class AIcInspectStorageBackupFacade(AIcBoundDataEntityCapabilityFacade):
    capability_id = INSPECT_STORAGE_BACKUP_CAPABILITY_ID

    def inspect_backup(self, backup_file: str) -> Mapping[str, object]:
        return self._invoke("inspect_backup", {"backup_file": backup_file})


class AIcRestoreStorageBackupFacade(AIcBoundDataEntityCapabilityFacade):
    capability_id = RESTORE_STORAGE_BACKUP_CAPABILITY_ID
    write_operation = True

    def restore_backup(self, backup_file: str, *, mode: str = "EMPTY_ONLY") -> Mapping[str, object]:
        return self._invoke("restore_backup", {"backup_file": backup_file, "mode": mode})


class AIcDataEntityProviderFacade:
    """Typed Data Entity API bound to exactly one provider instance.

    No operation is routed across provider instances.  The instance's access mode constrains
    mutating facades while its declared capability set determines which subfacades are available.
    """

    def __init__(
        self,
        provider: AIcProviderInstance,
        endpoints: AIcEndpointRegistry,
        dispatcher: AIcInvocationDispatcher,
        marshaller: AIcDataEntityMarshaller,
    ) -> None:
        self.provider = provider
        self.marshaller = marshaller
        self.invoker = AIcProviderCapabilityInvoker(provider, endpoints, dispatcher)
        self.get_record = AIcGetRecordFacade(self.invoker, marshaller) if provider.supports_capability(GET_RECORD_CAPABILITY_ID) else None
        self.query_records = AIcQueryRecordsFacade(self.invoker, marshaller) if provider.supports_capability(QUERY_RECORDS_CAPABILITY_ID) else None
        self.apply_changes = AIcApplyDirectRecordChangesFacade(self.invoker, marshaller) if provider.supports_capability(APPLY_DIRECT_RECORD_CHANGES_CAPABILITY_ID) else None
        self.inspect_storage_support = AIcInspectStorageSupportFacade(self.invoker) if provider.supports_capability(INSPECT_STORAGE_SUPPORT_CAPABILITY_ID) else None
        self.ensure_storage_support = AIcEnsureStorageSupportFacade(self.invoker) if provider.supports_capability(ENSURE_STORAGE_SUPPORT_CAPABILITY_ID) else None
        self.retire_storage_support = AIcRetireStorageSupportFacade(self.invoker) if provider.supports_capability(RETIRE_STORAGE_SUPPORT_CAPABILITY_ID) else None
        self.create_storage_backup = AIcCreateStorageBackupFacade(self.invoker) if provider.supports_capability(CREATE_STORAGE_BACKUP_CAPABILITY_ID) else None
        self.inspect_storage_backup = AIcInspectStorageBackupFacade(self.invoker) if provider.supports_capability(INSPECT_STORAGE_BACKUP_CAPABILITY_ID) else None
        self.restore_storage_backup = AIcRestoreStorageBackupFacade(self.invoker) if provider.supports_capability(RESTORE_STORAGE_BACKUP_CAPABILITY_ID) else None


def _raw_envelope(raw: object) -> AIcDataEntityEnvelope:
    if not isinstance(raw, Mapping):
        raise TypeError("Data Entity provider returned a non-object record")
    payload = raw.get("payload")
    if not isinstance(payload, Mapping):
        raise TypeError("Data Entity provider returned a non-object payload")
    return AIcDataEntityEnvelope(
        uid=str(raw["uid"]),
        schema_id=str(raw["schema_id"]),
        schema_version=int(raw["schema_version"]),
        record_revision=raw["record_revision"],
        state=AInDataEntityState(str(raw["state"])),
        payload=dict(payload),
    )
