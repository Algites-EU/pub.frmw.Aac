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

from .aic_bound_data_entity_capability_facade import AIcBoundDataEntityCapabilityFacade

APPLY_DIRECT_RECORD_CHANGES_CAPABILITY_ID = "_AAC.data-entity.apply-direct-record-changes"

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
