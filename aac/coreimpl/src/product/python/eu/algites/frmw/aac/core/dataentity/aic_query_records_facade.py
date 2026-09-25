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
from .aic_data_entity_query_page import AIcDataEntityQueryPage

T = TypeVar("T")

QUERY_RECORDS_CAPABILITY_ID = "_AAC.data-entity.query-records"

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
