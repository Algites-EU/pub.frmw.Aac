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

from .aic_data_entity_marshaller import AIcDataEntityMarshaller
from .aic_provider_capability_invoker import AIcProviderCapabilityInvoker

class AIcBoundDataEntityCapabilityFacade:
    capability_id: str
    capability_version = 1
    write_operation = False

    def __init__(self, invoker: AIcProviderCapabilityInvoker, marshaller: AIcDataEntityMarshaller | None = None) -> None:
        self.invoker = invoker
        self.marshaller = marshaller

    def _invoke(self, operation_id: str, arguments: Mapping[str, object]) -> Mapping[str, object]:
        if self.write_operation and self.invoker.provider.access_mode is AInProviderAccessMode.READ_ONLY:
            raise PermissionError(
                f"provider instance {self.invoker.provider.id!r} is configured READ_ONLY"
            )
        return self.invoker.invoke(self.capability_id, self.capability_version, operation_id, arguments)
