from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, Mapping, TypeVar
from uuid import uuid4
from eu.algites.frmw.aac.core.dataentity.api import (
    AIcDataEntityEnvelope,
    AIcDataEntityImplementationBinding,
    AIcDataEntityType,
    AIcDataEntityViewBinding,
    AIcTypedDataEntityEnvelope,
    AInDataEntityState,
)
from eu.algites.frmw.aac.core.instances.api import AIcProviderInstance, AInProviderAccessMode
from eu.algites.frmw.aac.core.invocation.api import AIcInvocationInput
from eu.algites.frmw.aac.core.capability.catalog import AIcActiveContractCatalog
from eu.algites.frmw.aac.core.invocation.dispatcher import AIcEndpointRegistry, AIcInvocationDispatcher
from eu.algites.frmw.aac.core.schemas.registry import AIcSchemaRegistry

from .aic_data_entity_implementation_registry import AIcDataEntityImplementationRegistry
from .aic_data_entity_view_registry import AIcDataEntityViewRegistry

T = TypeVar("T")

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
