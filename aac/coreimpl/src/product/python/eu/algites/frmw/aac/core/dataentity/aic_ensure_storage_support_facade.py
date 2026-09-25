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

ENSURE_STORAGE_SUPPORT_CAPABILITY_ID = "_AAC.data-entity.ensure-storage-support"

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
