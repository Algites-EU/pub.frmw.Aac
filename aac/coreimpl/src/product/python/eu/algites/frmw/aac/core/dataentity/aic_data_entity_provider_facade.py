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

from .aic_apply_direct_record_changes_facade import AIcApplyDirectRecordChangesFacade
from .aic_create_storage_backup_facade import AIcCreateStorageBackupFacade
from .aic_data_entity_marshaller import AIcDataEntityMarshaller
from .aic_ensure_storage_support_facade import AIcEnsureStorageSupportFacade
from .aic_get_record_facade import AIcGetRecordFacade
from .aic_inspect_storage_backup_facade import AIcInspectStorageBackupFacade
from .aic_inspect_storage_support_facade import AIcInspectStorageSupportFacade
from .aic_provider_capability_invoker import AIcProviderCapabilityInvoker
from .aic_query_records_facade import AIcQueryRecordsFacade
from .aic_restore_storage_backup_facade import AIcRestoreStorageBackupFacade
from .aic_retire_storage_support_facade import AIcRetireStorageSupportFacade

GET_RECORD_CAPABILITY_ID = "_AAC.data-entity.get-record"

QUERY_RECORDS_CAPABILITY_ID = "_AAC.data-entity.query-records"

APPLY_DIRECT_RECORD_CHANGES_CAPABILITY_ID = "_AAC.data-entity.apply-direct-record-changes"

INSPECT_STORAGE_SUPPORT_CAPABILITY_ID = "_AAC.data-entity.inspect-storage-support"

ENSURE_STORAGE_SUPPORT_CAPABILITY_ID = "_AAC.data-entity.ensure-storage-support"

RETIRE_STORAGE_SUPPORT_CAPABILITY_ID = "_AAC.data-entity.retire-storage-support"

CREATE_STORAGE_BACKUP_CAPABILITY_ID = "_AAC.data-entity.create-storage-backup"

INSPECT_STORAGE_BACKUP_CAPABILITY_ID = "_AAC.data-entity.inspect-storage-backup"

RESTORE_STORAGE_BACKUP_CAPABILITY_ID = "_AAC.data-entity.restore-storage-backup"

class AIcDataEntityProviderFacade:
    """Typed Data Entity API bound to exactly one provider instance.

    No operation is routed across provider instances.  The instance's access mode constrains
    mutating facades while its declared capability set determines which subfacades are available.
    """

    def __init__(
        self,
        provider: AIcProviderInstance,
        endpoints: AIcEndpointRegistry,
        dispatcher: AIcInvocationDispatcher,
        marshaller: AIcDataEntityMarshaller,
    ) -> None:
        self.provider = provider
        self.marshaller = marshaller
        self.invoker = AIcProviderCapabilityInvoker(provider, endpoints, dispatcher)
        self.get_record = AIcGetRecordFacade(self.invoker, marshaller) if provider.supports_capability(GET_RECORD_CAPABILITY_ID) else None
        self.query_records = AIcQueryRecordsFacade(self.invoker, marshaller) if provider.supports_capability(QUERY_RECORDS_CAPABILITY_ID) else None
        self.apply_changes = AIcApplyDirectRecordChangesFacade(self.invoker, marshaller) if provider.supports_capability(APPLY_DIRECT_RECORD_CHANGES_CAPABILITY_ID) else None
        self.inspect_storage_support = AIcInspectStorageSupportFacade(self.invoker) if provider.supports_capability(INSPECT_STORAGE_SUPPORT_CAPABILITY_ID) else None
        self.ensure_storage_support = AIcEnsureStorageSupportFacade(self.invoker) if provider.supports_capability(ENSURE_STORAGE_SUPPORT_CAPABILITY_ID) else None
        self.retire_storage_support = AIcRetireStorageSupportFacade(self.invoker) if provider.supports_capability(RETIRE_STORAGE_SUPPORT_CAPABILITY_ID) else None
        self.create_storage_backup = AIcCreateStorageBackupFacade(self.invoker) if provider.supports_capability(CREATE_STORAGE_BACKUP_CAPABILITY_ID) else None
        self.inspect_storage_backup = AIcInspectStorageBackupFacade(self.invoker) if provider.supports_capability(INSPECT_STORAGE_BACKUP_CAPABILITY_ID) else None
        self.restore_storage_backup = AIcRestoreStorageBackupFacade(self.invoker) if provider.supports_capability(RESTORE_STORAGE_BACKUP_CAPABILITY_ID) else None
