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

from .aic_data_entity_view_registry import AIcDataEntityViewRegistry
from .aic_data_entity_implementation_registry import AIcDataEntityImplementationRegistry
from .aic_data_entity_marshaller import AIcDataEntityMarshaller
from .aic_provider_capability_invoker import AIcProviderCapabilityInvoker
from .aic_bound_data_entity_capability_facade import AIcBoundDataEntityCapabilityFacade
from .aic_get_record_facade import AIcGetRecordFacade
from .aic_data_entity_query_page import AIcDataEntityQueryPage
from .aic_query_records_facade import AIcQueryRecordsFacade
from .aic_apply_direct_record_changes_facade import AIcApplyDirectRecordChangesFacade
from .aic_inspect_storage_support_facade import AIcInspectStorageSupportFacade
from .aic_ensure_storage_support_facade import AIcEnsureStorageSupportFacade
from .aic_retire_storage_support_facade import AIcRetireStorageSupportFacade
from .aic_create_storage_backup_facade import AIcCreateStorageBackupFacade
from .aic_inspect_storage_backup_facade import AIcInspectStorageBackupFacade
from .aic_restore_storage_backup_facade import AIcRestoreStorageBackupFacade
from .aic_data_entity_provider_facade import AIcDataEntityProviderFacade

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
