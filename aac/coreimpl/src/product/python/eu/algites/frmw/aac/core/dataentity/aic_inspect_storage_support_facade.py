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

INSPECT_STORAGE_SUPPORT_CAPABILITY_ID = "_AAC.data-entity.inspect-storage-support"

class AIcInspectStorageSupportFacade(AIcBoundDataEntityCapabilityFacade):
    capability_id = INSPECT_STORAGE_SUPPORT_CAPABILITY_ID

    def inspect(self, schema_id: str, schema_version: int) -> Mapping[str, object]:
        return self._invoke("inspect", {"schema_id": schema_id, "schema_version": schema_version})
