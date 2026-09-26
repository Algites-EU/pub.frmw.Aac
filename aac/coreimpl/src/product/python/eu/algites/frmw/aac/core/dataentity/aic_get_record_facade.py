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

T = TypeVar("T")

GET_RECORD_CAPABILITY_ID = "_AAC.data-entity.get-record"

def _raw_envelope(raw: object) -> AIcDataEntityEnvelope:
    if not isinstance(raw, Mapping):
        raise TypeError("Data Entity provider returned a non-object record")
    payload = raw.get("Payload")
    if not isinstance(payload, Mapping):
        raise TypeError("Data Entity provider returned a non-object payload")
    return AIcDataEntityEnvelope(
        uid=str(raw["Uid"]),
        schema_id=str(raw["SchemaId"]),
        schema_version=int(raw["SchemaVersion"]),
        record_revision=raw["RecordRevision"],
        state=AInDataEntityState(str(raw["State"])),
        payload=dict(payload),
    )

class AIcGetRecordFacade(AIcBoundDataEntityCapabilityFacade):
    capability_id = GET_RECORD_CAPABILITY_ID

    def get_raw(self, schema_id: str, uid: str) -> AIcDataEntityEnvelope | None:
        result = self._invoke("get", {"SchemaId": schema_id, "Uid": uid})
        raw = result.get("Record")
        return None if raw is None else _raw_envelope(raw)

    def get(self, data_type: AIcDataEntityType[T], uid: str) -> AIcTypedDataEntityEnvelope[T] | None:
        if self.marshaller is None:
            raise RuntimeError("typed Data Entity access requires a marshaller")
        raw = self.get_raw(data_type.schema_id, uid)
        return None if raw is None else self.marshaller.materialize(raw, data_type)
