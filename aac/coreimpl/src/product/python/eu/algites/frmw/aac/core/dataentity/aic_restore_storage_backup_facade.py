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

RESTORE_STORAGE_BACKUP_CAPABILITY_ID = "_AAC.data-entity.restore-storage-backup"

class AIcRestoreStorageBackupFacade(AIcBoundDataEntityCapabilityFacade):
    capability_id = RESTORE_STORAGE_BACKUP_CAPABILITY_ID
    write_operation = True

    def restore_backup(self, backup_file: str, *, mode: str = "EMPTY_ONLY") -> Mapping[str, object]:
        return self._invoke("restore_backup", {"backup_file": backup_file, "mode": mode})
