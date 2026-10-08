from __future__ import annotations

from eu.algites.frmw.aac.core.dataentity.aiig_data_entity_envelope_1 import AIigDataEntityEnvelope_1
from eu.algites.frmw.aac.core.dataentity.aiig_data_entity_get_record_request_1 import AIigDataEntityGetRecordRequest_1
from eu.algites.frmw.aac.core.dataentity.aiig_data_entity_get_record_result_1 import AIigDataEntityGetRecordResult_1
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
    payload = raw.get(AIigDataEntityEnvelope_1.SCHEMA_FIELD_NAME__PAYLOAD)
    if not isinstance(payload, Mapping):
        raise TypeError("Data Entity provider returned a non-object payload")
    return AIcDataEntityEnvelope(
        uid=str(raw[AIigDataEntityEnvelope_1.SCHEMA_FIELD_NAME__UID]),
        schema_id=str(raw[AIigDataEntityEnvelope_1.SCHEMA_FIELD_NAME__SCHEMA_ID]),
        schema_version=int(raw[AIigDataEntityEnvelope_1.SCHEMA_FIELD_NAME__SCHEMA_VERSION]),
        record_revision=raw[AIigDataEntityEnvelope_1.SCHEMA_FIELD_NAME__RECORD_REVISION],
        state=AInDataEntityState(str(raw[AIigDataEntityEnvelope_1.SCHEMA_FIELD_NAME__STATE])),
        payload=dict(payload),
    )

class AIcGetRecordFacade(AIcBoundDataEntityCapabilityFacade):
    capability_id = GET_RECORD_CAPABILITY_ID

    def get_raw(self, schema_id: str, uid: str) -> AIcDataEntityEnvelope | None:
        result = self._invoke("get", {AIigDataEntityGetRecordRequest_1.SCHEMA_FIELD_NAME__SCHEMA_ID: schema_id, AIigDataEntityGetRecordRequest_1.SCHEMA_FIELD_NAME__UID: uid})
        raw = result.get(AIigDataEntityGetRecordResult_1.SCHEMA_FIELD_NAME__RECORD)
        return None if raw is None else _raw_envelope(raw)

    def get(self, data_type: AIcDataEntityType[T], uid: str) -> AIcTypedDataEntityEnvelope[T] | None:
        if self.marshaller is None:
            raise RuntimeError("typed Data Entity access requires a marshaller")
        raw = self.get_raw(data_type.schema_id, uid)
        return None if raw is None else self.marshaller.materialize(raw, data_type)
