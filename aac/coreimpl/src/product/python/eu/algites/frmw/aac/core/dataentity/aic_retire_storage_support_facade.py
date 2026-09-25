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

RETIRE_STORAGE_SUPPORT_CAPABILITY_ID = "_AAC.data-entity.retire-storage-support"

class AIcRetireStorageSupportFacade(AIcBoundDataEntityCapabilityFacade):
    capability_id = RETIRE_STORAGE_SUPPORT_CAPABILITY_ID
    write_operation = True

    def retire(self, schema_id: str, schema_version: int) -> Mapping[str, object]:
        return self._invoke("retire", {"schema_id": schema_id, "schema_version": schema_version})
